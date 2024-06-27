import re
from flask import Flask, render_template, session, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required

from mysqldb import DBConnector
import mysql.connector

app = Flask(__name__)
application = app
app.config.from_pyfile('config.py')

db_connector = DBConnector(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message = "Войдите, чтобы просматривать содержимое данной страницы"
login_manager.login_message_category = "warning"

class User(UserMixin):
    def __init__(self, user_id, login):
        self.id = user_id
        self.login = login

@login_manager.user_loader
def load_user(user_id):
    user = get_user(user_id)

    if user:
        return User(user_id, user.login)

    return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    login = request.form.get("login", "")
    password = request.form.get("password", "")
    remember = request.form.get("remember") == "on"

    query = 'SELECT id, login FROM users WHERE login=%s AND password_hash=SHA2(%s, 256)'


    with db_connector.connect().cursor(named_tuple=True) as cursor:

        cursor.execute(query, (login, password))

        user = cursor.fetchone()

    if user:
        login_user(User(user.id, user.login), remember=remember)
        flash("Успешная авторизация", category="success")
        target_page = request.args.get("next", url_for("index"))
        return redirect(target_page)

    flash("Введены некорректные учётные данные пользователя", category="danger")

    return render_template("login.html")


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for("index"))

@app.route('/users')
def users_list():
    return render_template("users.html", users=get_users())

def get_users():
    query = '''
    SELECT users.id, login, last_name, first_name, middle_name, roles.name as role_name
    FROM users
    LEFT JOIN roles ON users.role_id = roles.id
    '''

    with db_connector.connect().cursor(named_tuple=True) as cursor:

        cursor.execute(query)

        users = cursor.fetchall()

    return users

def get_roles():
    query = '''
    SELECT id, name FROM roles
    '''

    try:
        with db_connector.connect().cursor(named_tuple=True) as cursor:
            cursor.execute(query)
            roles = cursor.fetchall()
        return roles
    except mysql.connector.Error as e:
        flash(f"Database error: {e}", 'warning')
        return []
    except Exception as e:
        flash(f"An error occurred: {e}", 'warning')
        return []

@app.route("/create_user", methods=["GET", "POST"])
@login_required
def create_user():
    errors = {}

    if request.method == "GET":
        return render_template("create_user.html", user=None, roles=get_roles(), errors=errors)

    login = request.form.get("login", "")
    password = request.form.get("password", "")
    last_name = request.form.get("last_name", "")
    first_name = request.form.get('first_name', "")
    middle_name = request.form.get('middle_name', "")
    role_id = request.form.get('role_id')

    errors = validate_user_data(login, password, last_name, first_name)

    if errors:
        return render_template("create_user.html", roles=get_roles(), errors=errors)

    query = '''
    INSERT INTO users (login, password_hash, last_name, first_name {middle_name_placeholder} {role_id_placeholder})
    VALUES (%s, SHA2(%s, 256), %s, %s {middle_name_value} {role_id_value})
    '''

    placeholders = {
        'middle_name_placeholder': ', middle_name' if middle_name else '',
        'role_id_placeholder': ', role_id' if role_id else '',
        'middle_name_value': ', %s' if middle_name else '',
        'role_id_value': ', %s' if role_id else '',
    }

    query = query.format(**placeholders)

    parameters = [login, password, last_name, first_name]
    if middle_name:
        parameters.append(middle_name)

    if role_id:
        parameters.append(role_id)

    try:
        cursor = db_connector.connect().cursor(named_tuple=True)
        cursor.execute(query, tuple(parameters))
        cursor.close()
        db_connector.connect().commit()
        flash('Пользователь успешно создан', 'success')
        return redirect(url_for('users_list'))
    except Exception as e:
        flash(f"Ошибка! {e}", 'warning')
        return render_template("create_user.html", user=None, roles=get_roles(), errors=errors)

def validate_password(password):
    if len(password) < 8:
        return 'Пароль должен иметь длину не менее 8 символов'
    if len(password) > 128:
        return 'Пароль должен иметь длину не более 128 символов'
    if not ((re.search(r'[a-z]', password) or re.search(r'[а-я]', password)) and (re.search(r'[А-Я]', password) or re.search(r'[A-Z]', password))):
        return 'Пароль должен содержать как минимум одну заглавную и одну строчную букву'
    if not re.search(r'\d', password):
        return 'Пароль должен содержать как минимум одну цифру'
    if ' ' in password:
        return 'Пароль не должен содержать пробелы'
    if not re.match(r'^[\w~!?@#$%^&*_\-+()\[\]{}><\/\\|"\'.,:;]*$', password):
        return 'Пароль может содержать только следующие доп. символы: ~ ! ? @ # $ % ^ & * _ - + ( ) [ ] { } > < / \ | " \' . , : ;'
    return ""

@app.route('/users/<int:user_id>/info')
def user_info(user_id):
    user = get_user(user_id)
    if user:
        return render_template("user_info.html", user=user)
    return render_template(url_for("users_list"))

def get_user(user_id):
    query = '''
    SELECT users.id, login, last_name, first_name, middle_name, users.role_id as role_id, roles.name as role_name
    FROM users
    LEFT JOIN roles ON users.role_id = roles.id
    WHERE users.id=%s
    '''

    try:
        with db_connector.connect().cursor(named_tuple=True) as cursor:
            cursor.execute(query, (user_id,))
            user = cursor.fetchone()
        return user
    except mysql.connector.Error as e:
        flash(f"Database error: {e}", 'warning')
        return None
    except Exception as e:
        flash(f"An error occurred: {e}", 'warning')
        return None

@app.route('/users/<int:user_id>/edit_user', methods=["GET", "POST"])
@login_required
def edit_user(user_id):
    user = get_user(user_id)
    roles = get_roles()
    errors = {}
    if request.method == 'GET':
        return render_template("edit_user.html", user=user, errors=errors, roles=roles)

    last_name = request.form.get("last_name", "")
    first_name = request.form.get('first_name', "")
    middle_name = request.form.get('middle_name', "")
    role_id = request.form.get('role_id')
    errors = validate_user_data(login=None, password=None, last_name=last_name, first_name=first_name)

    if errors:
        return render_template("edit_user.html", user=user, roles=roles, errors=errors)

    query = '''
    UPDATE users
    SET last_name=%s, first_name=%s, role_id={role_id_value} {middle_name_placeholder}{middle_name_value}
    WHERE id=%s
    '''

    placeholders = {
        'middle_name_placeholder': ', middle_name=' if middle_name else '',
        'middle_name_value': '%s' if middle_name else '',
        'role_id_value': '%s' if role_id else 'NULL',
    }

    query = query.format(**placeholders)

    parameters = [last_name, first_name]
    if role_id:
        parameters.append(role_id)

    if middle_name:
        parameters.append(middle_name)

    parameters.append(user_id)

    try:
        with db_connector.connect().cursor(named_tuple=True) as cursor:
            cursor.execute(query, tuple(parameters))
            db_connector.connect().commit()
        flash('Пользователь успешно обновлен', 'success')
        return redirect(url_for('users_list'))
    except mysql.connector.errors.OperationalError as oe:
        db_connector.connect().rollback()
        flash(f"Операционная ошибка! {oe}", 'warning')
        return render_template("edit_user.html", user=user, roles=get_roles(), errors=errors)
    except Exception as e:
        db_connector.connect().rollback()
        flash(f"Ошибка! {e}", 'warning')
        return render_template("edit_user.html", user=user, roles=get_roles(), errors=errors)

@app.route("/change_password", methods=["GET", "POST"])
@login_required
def change_password():
    errors = {}
    if request.method == 'GET':
        return render_template("change_password.html", errors=errors)

    old_password = request.form.get("old_password", "")
    new_password = request.form.get("new_password", "")
    new_password2 = request.form.get("new_password2", "")

    query_check_password = "SELECT IF(SHA2(%s, 256)=password_hash, 1, 0) as valid FROM users WHERE id=%s"

    try:
        with db_connector.connect().cursor(named_tuple=True) as cursor:

            cursor.execute(query_check_password, (old_password, current_user.id))

            result = cursor.fetchone()

            if not result.valid:
                errors["old_password"] = "Неверный пароль!"
                flash("Ошибка! Введен неверный пароль!", 'warning')
                return render_template("change_password.html", errors=errors)
    except Exception as e:
        flash(f"Ошибка! {e}", 'warning')
        return render_template("change_password.html", errors=errors)

    new_password_validate_error = validate_password(new_password)
    if new_password_validate_error != "":
        errors["new_password"] = new_password_validate_error
        flash("Ошибка! Новый пароль не соответствует требованиям!", 'warning')
        return render_template("change_password.html", errors=errors)

    if new_password != new_password2:
        errors["new_password"] = "Пароли не совпадают"
        errors["new_password2"] = "Пароли не совпадают"
        flash("Введенные пароли не совпадают!", "warning")
        return render_template("change_password.html", errors=errors)

    change_password_query = "UPDATE users SET password_hash=SHA2(%s, 256) WHERE id=%s"

    try:
        cursor = db_connector.connect().cursor(named_tuple=True)
        cursor.execute(change_password_query, (new_password, current_user.id))
        cursor.close()
        db_connector.connect().commit()
        flash('Пароль успешно обновлен', 'success')
        return redirect(url_for('users_list'))
    except Exception as e:
        flash(f"Ошибка! {e}", 'warning')
        return render_template("change_password.html", errors=errors)


@app.route("/delete_user/<int:user_id>", methods=["POST"])
@login_required
def delete_user(user_id):
    query = "DELETE FROM users WHERE id=%s"

    try:
        cursor = db_connector.connect().cursor(named_tuple=True)
        cursor.execute(query, (user_id,))
        cursor.close()
        db_connector.connect().commit()
        flash('Пользователь успешно удален', 'success')
    except Exception as e:
        flash(f"Ошибка! {e}", 'warning')

    return redirect(url_for('users_list'))

def validate_user_data(login, password, last_name, first_name):
    errors = {}
    if login is not None:
        if login == "":
            errors["login"] = "Поле не может быть пустым"
        elif len(login) < 5:
            errors["login"] = "Логин должен иметь длину не менее 5 символов"
        elif not re.match("^[a-zA-Z0-9]+$", login):
            errors["login"] = "Логин должен состоять только из латинских букв и цифр"

    if password is not None:
        password_validate_error = validate_password(password)
        if password_validate_error != "":
            errors["password"] = password_validate_error

    if last_name == "":
        errors["last_name"] = "Поле не может быть пустым"

    if first_name == "":
        errors["first_name"] = "Поле не может быть пустым"

    return errors
