from flask import Flask, render_template, session, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from mysqldb import DatabaseConnector
import os
import hashlib
import bleach
#import jsonify

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
    def __init__(self, user_id, username, first_name, middle_name, last_name):
        self.id = user_id
        self.username = username
        self.first_name = first_name
        self.middle_name = middle_name
        self.last_name = last_name

    def get_id(self):
        return str(self.id)


@login_manager.user_loader
def load_user(user_id):
    cnx = db.connect()
    with cnx.cursor(named_tuple=True) as cursor:
        cursor.execute("SELECT id, username, first_name, middle_name, last_name FROM Users WHERE id = %s", (user_id,))
        user_data = cursor.fetchone()
    if user_data:
        return User(user_data.id, user_data.username, user_data.first_name, user_data.middle_name, user_data.last_name)
    return None


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user_login = request.form['login']
        user_password = request.form['password']
        check_remember = True if request.form.get('remember_me') else False
        cnx = db.connect()
        with cnx.cursor(named_tuple=True) as cursor:
            query = "SELECT id, username,  first_name, middle_name, last_name FROM Users WHERE username = %s AND password_hash = SHA2(%s, 256)"
            cursor.execute(query, (user_login, user_password))
            user_data = cursor.fetchone()
        if user_data:
            user = User(user_data.id, user_data.username, user_data.first_name, user_data.middle_name, user_data.last_name)
            login_user(user, remember=check_remember)
            flash("Вход выполнен успешно", "success")
            return redirect(request.args.get('next', url_for('index')))
        flash('Введён неправильный логин или пароль', 'danger')
    return render_template('login.html')

@app.route('/logout', methods=['GET'])
def logout():
    logout_user()
    return redirect(url_for('index'))



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
                AVG(r.rating) as average_rating,
                COUNT(r.id) as reviews_count
            FROM Books b
            LEFT JOIN Reviews r ON b.id = r.book_id
            GROUP BY b.id
            ORDER BY b.year DESC
            LIMIT %s OFFSET %s
        """
        cursor.execute(query, (per_page, offset))
        books = cursor.fetchall()

        cursor.execute("SELECT COUNT(*) as total FROM Books")
        total_books = cursor.fetchone().total

    total_pages = (total_books + per_page - 1) // per_page
    return render_template('index.html', books=books, page=page, total_pages=total_pages)

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
def add_book():
    if request.method == 'POST':
        title = request.form['title']
        author = request.form['author']
        year = request.form['year']
        publisher = request.form['publisher']
        pages = request.form['pages']
        description = request.form['description']
        cover = request.files['cover']

        cover_id = None

        if cover:
            cover_md5 = get_md5(cover)
            filename = cover.filename
            mime_type = cover.content_type

            cnx = db.connect()
            cursor = cnx.cursor()
            cursor.execute("SELECT id FROM Covers WHERE md5_hash = %s", (cover_md5,))
            result = cursor.fetchone()

            if result:
                cover_id = result[0]
            else:
                cursor.execute("INSERT INTO Covers (filename, mime_type, md5_hash) VALUES (%s, %s, %s)", (filename, mime_type, cover_md5))
                cover_id = cursor.lastrowid
                cnx.commit()

                # Save the file using the ID as filename
                cover_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{cover_id}")
                cover.save(cover_path)

        try:
            cursor.execute("INSERT INTO Books (title, author, year, publisher, pages, description, cover_id) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                           (title, author, year, publisher, pages, description, cover_id))
            cnx.commit()
            flash("Книга успешно добавлена", "success")
            return redirect('/')
        except db.connector.Error as err:
            cnx.rollback()
            flash(f"При сохранении данных возникла ошибка: {err}", "danger")
        finally:
            cursor.close()
            cnx.close()

    return render_template('add_book.html')


@app.route('/edit/<int:book_id>', methods=['GET', 'POST'])
def edit_book(book_id):
    cnx = db.connect()
    cursor = cnx.cursor(dictionary=True)

    if request.method == 'POST':
        # Получаем новые данные из формы
        title = request.form['title']
        author = request.form['author']
        year = request.form['year']
        publisher = request.form['publisher']
        pages = request.form['pages']
        description = bleach.clean(request.form['description'], strip=True)

        try:
            # Обновляем данные книги в базе данных
            cursor.execute("""
                UPDATE Books
                SET title = %s, author = %s, year = %s, publisher = %s, pages = %s, description = %s
                WHERE id = %s
            """, (title, author, year, publisher, pages, description, book_id))
            cnx.commit()
            flash("Данные книги успешно обновлены", "success")
            return redirect(url_for('index'))
        except db.connector.Error as err:
            cnx.rollback()
            flash(f"При обновлении данных возникла ошибка: {err}", "danger")
        finally:
            cursor.close()
            cnx.close()

    # Загружаем данные книги для отображения на странице редактирования
    cursor.execute("SELECT * FROM Books WHERE id = %s", (book_id,))
    book = cursor.fetchone()
    return render_template('edit_book.html', book=book)

@app.route('/delete/<int:book_id>', methods=['DELETE'])
@login_required
def delete_book(book_id):
    cnx = db.connect()
    cursor = cnx.cursor()

    try:
        #cursor.execute("DELETE FROM Reviews WHERE book_id = %s", (book_id,))
        cursor.execute("DELETE FROM BookGenres WHERE book_id = %s", (book_id,))
        cursor.execute("SELECT cover_id FROM Books WHERE id = %s", (book_id,))
        cover_id = cursor.fetchone()[0]
        cursor.execute("DELETE FROM Books WHERE id = %s", (book_id,))
        cnx.commit()
        if cover_id:
            cover_path = os.path.join(app.config['UPLOAD_FOLDER'], str(cover_id))
            if os.path.exists(cover_path):
                os.remove(cover_path)

        flash("Книга успешно удалена", "success")
    except db.connector.Error as err:
        cnx.rollback()
        flash(f"При удалении книги возникла ошибка: {err}", "danger")
    finally:
        cursor.close()
        cnx.close()

    return jsonify({'message': 'Книга успешно удалена'}), 200

@app.route('/book/<int:book_id>')
def view_book(book_id):
    cnx = db.connect()
    with cnx.cursor(named_tuple=True) as cursor:
        # Получаем информацию о книге и средней оценке
        cursor.execute("""
            SELECT b.*, c.filename as cover_filename,
                   AVG(r.rating) AS average_rating, COUNT(r.id) AS reviews_count
            FROM Books b
            LEFT JOIN Covers c ON b.cover_id = c.id
            LEFT JOIN Reviews r ON b.id = r.book_id
            WHERE b.id = %s
            GROUP BY b.id
        """, (book_id,))
        book = cursor.fetchone()

        # Получаем рецензии книги
        cursor.execute("""
            SELECT r.rating, r.text, u.username as user_name
            FROM Reviews r
            JOIN Users u ON r.user_id = u.id
            WHERE r.book_id = %s
        """, (book_id,))
        reviews = cursor.fetchall()

    return render_template('book.html', book=book, reviews=reviews)



if __name__ == '__main__':
    app.run(debug=True)
