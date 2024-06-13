from flask import Flask, render_template, session, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from mysqldb import DatabaseConnector
import os
import hashlib
import bleach

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
        except mysql.connector.Error as err:
            cnx.rollback()
            flash(f"При сохранении данных возникла ошибка: {err}", "danger")
        finally:
            cursor.close()
            cnx.close()

    return render_template('add_book.html')


if __name__ == '__main__':
    app.run(debug=True)
