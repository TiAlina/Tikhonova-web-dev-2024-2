from flask import Flask, render_template, request, redirect, url_for, flash, abort
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from mysqldb import DatabaseConnector
from functools import wraps
import os
import hashlib
import bleach
import markdown2

app = Flask(__name__)
application = app

app.config.from_pyfile('config.py')
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Для доступа к этой странице нужно авторизироваться.'
login_manager.login_message_category = 'warning'
db = DatabaseConnector(app)

class User(UserMixin):
    def __init__(self, user_id, username, first_name, middle_name, last_name, role_id):
        self.id = user_id
        self.username = username
        self.first_name = first_name
        self.middle_name = middle_name
        self.last_name = last_name
        self.role_id = role_id

    def get_id(self):
        return str(self.id)

@login_manager.user_loader
def load_user(user_id):
    cnx = db.connect()
    with cnx.cursor(named_tuple=True) as cursor:
        cursor.execute("SELECT id, username, first_name, middle_name, last_name, role_id FROM Users WHERE id = %s", (user_id,))
        user_data = cursor.fetchone()
    if user_data:
        return User(user_data.id, user_data.username, user_data.first_name, user_data.middle_name, user_data.last_name, user_data.role_id)
    return None

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user_login = bleach.clean(request.form['login'])
        user_password = bleach.clean(request.form['password'])
        check_remember = True if request.form.get('remember_me') else False
        cnx = db.connect()
        with cnx.cursor(named_tuple=True) as cursor:
            query = "SELECT id, username,  first_name, middle_name, last_name, role_id FROM Users WHERE username = %s AND password_hash = SHA2(%s, 256)"
            cursor.execute(query, (user_login, user_password))
            user_data = cursor.fetchone()
        if user_data:
            user = User(user_data.id, user_data.username, user_data.first_name, user_data.middle_name, user_data.last_name, user_data.role_id)
            login_user(user, remember=check_remember)
            flash("Вход выполнен успешно", "success")
            return redirect(request.args.get('next', url_for('index')))
        flash('Введён неправильный логин или пароль', 'danger')
    return render_template('login.html')

def admin_required(func):
    @wraps(func)
    def decorated_view(*args, **kwargs):
        if current_user.is_authenticated and current_user.role_id == 1:
            return func(*args, **kwargs)
        else:
            abort(403)
    return decorated_view

def moderator_required(func):
    @wraps(func)
    def decorated_view(*args, **kwargs):
        if current_user.is_authenticated and current_user.role_id in [1, 2]:
            return func(*args, **kwargs)
        else:
            abort(403)
    return decorated_view

@app.errorhandler(403)
def forbidden(error):
    flash("У вас нет прав доступа к этой странице", "danger")
    return redirect(url_for('index'))

@app.route('/logout', methods=['GET'])
def logout():
    logout_user()
    return redirect(url_for('index'))


def get_user_role(user_id):
    cnx = db.connect()
    with cnx.cursor() as cursor:
        cursor.execute("SELECT name FROM Roles WHERE id = %s", (user_id,))
        role = cursor.fetchone()
        if role:
            return role[0]
    return None

@app.context_processor
def utility_processor():
    def get_user_role(role_id):
        cnx = db.connect()
        try:
            with cnx.cursor() as cursor:
                cursor.execute("SELECT name FROM Roles WHERE id = %s", (role_id,))
                role_name = cursor.fetchone()
                return role_name[0] if role_name else None
        finally:
            cnx.close()

    return dict(get_user_role=get_user_role)

@app.route('/')
@app.route('/page/<int:page>')
def index(page=1):
    per_page = 10
    offset = (page - 1) * per_page
    cnx = db.connect()
    with cnx.cursor(named_tuple=True) as cursor:
        query = """
            SELECT
                b.id, b.title, b.year,
                (SELECT FORMAT(AVG(r.rating), 1) FROM Reviews r WHERE r.book_id = b.id) AS average_rating,
                (SELECT COUNT(r.id) FROM Reviews r WHERE r.book_id = b.id) AS reviews_count,
                COALESCE((SELECT GROUP_CONCAT(DISTINCT g.name SEPARATOR ', ')
                          FROM Genres g
                          JOIN BookGenres bg ON g.id = bg.genre_id
                          WHERE bg.book_id = b.id), '') AS genres
            FROM Books b
            ORDER BY b.year DESC
            LIMIT %s OFFSET %s
        """
        cursor.execute(query, (per_page, offset))
        books = cursor.fetchall()

        cursor.execute("SELECT COUNT(*) as total FROM Books")
        total_books = cursor.fetchone().total

    total_pages = (total_books + per_page - 1) // per_page
    return render_template('index.html', books=books, page=page, total_pages=total_pages, get_user_role=get_user_role)



def get_reviews_stats():
    cnx = db.connect()
    with cnx.cursor(named_tuple=True) as cursor:
        cursor.execute("""
            SELECT
                book_id,
                COUNT(*) AS reviews_count,
                FORMAT(AVG(rating), 1) AS average_rating
            FROM
                Reviews
            GROUP BY
                book_id
        """)
        reviews_stats = cursor.fetchall()
    return reviews_stats


def get_md5(file):
    file.seek(0)
    file_hash = hashlib.md5()
    while chunk := file.read(8192):
        file_hash.update(chunk)
    file.seek(0)
    return file_hash.hexdigest()

@app.route('/add', methods=['GET', 'POST'])
@login_required
def add_book():
    if get_user_role(current_user.role_id) != 'admin':
        abort(403)

    cnx = db.connect()
    cursor = cnx.cursor(named_tuple=True)

    cursor.execute("SELECT id, name FROM Genres")
    genres = cursor.fetchall()

    if request.method == 'POST':
        title = bleach.clean(request.form['title'])
        author = bleach.clean(request.form['author'])
        year = bleach.clean(request.form['year'])
        publisher = request.form['publisher']
        pages = bleach.clean(request.form['pages'])
        description = bleach.clean(request.form['description'])
        cover = request.files['cover']
        genre_ids = request.form.getlist('genres')

        cover_id = None
        if cover:
            cover_md5 = get_md5(cover)
            filename = cover.filename
            mime_type = cover.content_type

            cursor.execute("SELECT id FROM Covers WHERE md5_hash = %s", (cover_md5,))
            result = cursor.fetchone()

            if result:
                cover_id = result.id
            else:
                cursor.execute("INSERT INTO Covers (filename, mime_type, md5_hash) VALUES (%s, %s, %s)",
                               (filename, mime_type, cover_md5))
                cover_id = cursor.lastrowid
                cnx.commit()

                cover_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{cover_id}")
                cover.save(cover_path)

        try:
            cursor.execute("INSERT INTO Books (title, author, year, publisher, pages, description, cover_id) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                           (title, author, year, publisher, pages, description, cover_id))
            book_id = cursor.lastrowid

            for genre_id in genre_ids:
                cursor.execute("INSERT INTO BookGenres (book_id, genre_id) VALUES (%s, %s)", (book_id, genre_id))

            cnx.commit()
            flash("Книга успешно добавлена", "success")
            return redirect('/')
        except db.connector.Error as err:
            cnx.rollback()
            flash(f"При сохранении данных возникла ошибка: {err}", "danger")
        finally:
            cursor.close()
            cnx.close()

    return render_template('add_book.html', genres=genres)



@app.route('/edit/<int:book_id>', methods=['GET', 'POST'])
@login_required
def edit_book(book_id):
    if get_user_role(current_user.role_id) not in ['admin', 'moderator']:
        abort(403)

    cnx = db.connect()
    cursor = cnx.cursor(dictionary=True)

    if request.method == 'POST':
        title = bleach.clean(request.form['title'])
        author = bleach.clean(request.form['author'])
        year = bleach.clean(request.form['year'])
        publisher = bleach.clean(request.form['publisher'])
        pages = bleach.clean(request.form['pages'])
        description = bleach.clean(request.form['description'], strip=True)
        genre_ids = request.form.getlist('genres')

        try:
            cursor.execute("""
                UPDATE Books
                SET title = %s, author = %s, year = %s, publisher = %s, pages = %s, description = %s
                WHERE id = %s
            """, (title, author, year, publisher, pages, description, book_id))
            cnx.commit()

            cursor.execute("DELETE FROM BookGenres WHERE book_id = %s", (book_id,))

            for genre_id in genre_ids:
                cursor.execute("INSERT INTO BookGenres (book_id, genre_id) VALUES (%s, %s)", (book_id, genre_id))
            cnx.commit()

            flash("Данные книги успешно обновлены", "success")
            return redirect(url_for('index'))
        except db.connector.Error as err:
            cnx.rollback()
            flash(f"При обновлении данных возникла ошибка: {err}", "danger")
        finally:
            cursor.close()
            cnx.close()

    cursor.execute("SELECT * FROM Books WHERE id = %s", (book_id,))
    book = cursor.fetchone()

    cursor.execute("SELECT id, name FROM Genres")
    genres = cursor.fetchall()


    cursor.execute("SELECT genre_id FROM BookGenres WHERE book_id = %s", (book_id,))
    selected_genres = [genre['genre_id'] for genre in cursor.fetchall()]

    return render_template('edit_book.html', book=book, genres=genres, selected_genres=selected_genres)



@app.route('/delete/<int:book_id>', methods=['POST'])
@login_required
def delete_book(book_id):
    if get_user_role(current_user.role_id) != 'admin':
        abort(403)

    cnx = db.connect()
    cursor = cnx.cursor()

    try:
        cursor.execute("SELECT cover_id FROM Books WHERE id = %s", (book_id,))
        row = cursor.fetchone()
        if row:
            cover_id = row[0]


            cursor.execute("DELETE FROM BookGenres WHERE book_id = %s", (book_id,))

            cursor.execute("DELETE FROM Books WHERE id = %s", (book_id,))
            cnx.commit()


            if cover_id:
                cover_path = os.path.join(app.config['UPLOAD_FOLDER'], str(cover_id))
                if os.path.exists(cover_path):
                    os.remove(cover_path)

            flash("Книга успешно удалена", "success")
        else:
            flash("Книга не найдена", "danger")
    except db.connector.Error as err:
        cnx.rollback()
        flash(f"При удалении книги возникла ошибка: {err}", "danger")
    finally:
        cursor.close()
        cnx.close()

    return redirect(url_for('index'))



@app.route('/book/<int:book_id>')
def view_book(book_id):
    cnx = db.connect()
    with cnx.cursor(named_tuple=True) as cursor:
        cursor.execute("""
            SELECT b.*, c.filename as cover_filename,
                   FORMAT(AVG(r.rating), 1) AS average_rating, COUNT(DISTINCT r.id) AS reviews_count,
                   COALESCE(GROUP_CONCAT(DISTINCT g.name SEPARATOR ', '), '') as genres
            FROM Books b
            LEFT JOIN Covers c ON b.cover_id = c.id
            LEFT JOIN Reviews r ON b.id = r.book_id
            LEFT JOIN BookGenres bg ON b.id = bg.book_id
            LEFT JOIN Genres g ON bg.genre_id = g.id
            WHERE b.id = %s
            GROUP BY b.id, c.filename
        """, (book_id,))
        book = cursor.fetchone()

        if book and book.description:
            html_description = markdown2.markdown(book.description)
            book = book._replace(description=html_description)

        cursor.execute("""
            SELECT r.rating, r.text, u.username as user_name
            FROM Reviews r
            JOIN Users u ON r.user_id = u.id
            WHERE r.book_id = %s
        """, (book_id,))
        reviews = cursor.fetchall()

        cursor.execute("""
            SELECT r.rating, r.text
            FROM Reviews r
            WHERE r.book_id = %s AND r.user_id = %s
        """, (book_id, current_user.id if current_user.is_authenticated else None))
        user_review = cursor.fetchone()

        cursor.execute("""
            SELECT id, name
            FROM Collections
            WHERE user_id = %s
        """, (current_user.id if current_user.is_authenticated else None,))
        collections = cursor.fetchall()

    return render_template('book.html', book=book, reviews=reviews, user_review=user_review, collections=collections, get_user_role=get_user_role)



@app.route('/book/<int:book_id>/add_to_collection', methods=['POST'])
@login_required
def add_to_collection(book_id):
    collection_id = request.form['collection_id']
    cnx = db.connect()
    with cnx.cursor(named_tuple=True) as cursor:
        cursor.execute("""
            INSERT INTO BookCollections (book_id, collection_id)
            VALUES (%s, %s)
        """, (book_id, collection_id))
        cnx.commit()
    flash('Книга успешно добавлена в подборку!', 'success')
    return redirect(url_for('view_book', book_id=book_id))



@app.route('/book/<int:book_id>/add_review', methods=['GET', 'POST'])
@login_required
def add_review(book_id):
    user_id = current_user.id
    if request.method == 'POST':
        rating_text = request.form['rating']
        ratings = {
            'отлично': 5,
            'хорошо': 4,
            'удовлетворительно': 3,
            'неудовлетворительно': 2,
            'плохо': 1,
            'ужасно': 0
        }
        rating = ratings.get(rating_text.lower(), None)
        if rating is None:
            flash('Некорректное значение оценки!', 'error')
            return redirect(url_for('add_review', book_id=book_id))
        text = bleach.clean(request.form['text'])
        cnx = db.connect()
        with cnx.cursor(named_tuple=True) as cursor:
            cursor.execute("""
                INSERT INTO Reviews (book_id, user_id, rating, text)
                VALUES (%s, %s, %s, %s)
            """, (book_id, user_id, rating, text))
            cnx.commit()
        flash('Рецензия успешно добавлена!', 'success')
        return redirect(url_for('view_book', book_id=book_id))

    return render_template('add_review.html', book_id=book_id)


@app.route('/collections')
@login_required
def collections():
    if get_user_role(current_user.role_id) != 'user':
        abort(403)
    else:
        cnx = db.connect()
        with cnx.cursor(named_tuple=True) as cursor:
            cursor.execute("""
                SELECT c.id, c.name, COUNT(bc.book_id) AS books_count
                FROM Collections c
                LEFT JOIN BookCollections bc ON c.id = bc.collection_id
                WHERE c.user_id = %s
                GROUP BY c.id
            """, (current_user.id,))
            collections = cursor.fetchall()

        return render_template('collections.html', collections=collections)


@app.route('/collections/add', methods=['POST'])
@login_required
def add_collection():
    if get_user_role(current_user.role_id) != 'user':
        abort(403)
    else:
        collection_name = request.form['name']
        cnx = db.connect()
        with cnx.cursor(named_tuple=True) as cursor:
            cursor.execute("""
                INSERT INTO Collections (name, user_id)
                VALUES (%s, %s)
            """, (collection_name, current_user.id))
            cnx.commit()
        flash('Подборка успешно добавлена!', 'success')
        return redirect(url_for('collections'))


@app.route('/collections/<int:collection_id>')
@login_required
def view_collection(collection_id):
    cnx = db.connect()
    with cnx.cursor(named_tuple=True) as cursor:
        cursor.execute("""
            SELECT b.id, b.title, b.description
            FROM Books b
            JOIN BookCollections bc ON b.id = bc.book_id
            WHERE bc.collection_id = %s
        """, (collection_id,))
        books = cursor.fetchall()

        cursor.execute("""
            SELECT name
            FROM Collections
            WHERE id = %s
        """, (collection_id,))
        collection = cursor.fetchone()

    if not collection:
        flash('Подборка не найдена или у вас нет доступа к этой подборке.', 'danger')
        return redirect(url_for('collections'))

    return render_template('collection_books.html', books=books, collection=collection)


if __name__ == '__main__':
    app.run(debug=True)
