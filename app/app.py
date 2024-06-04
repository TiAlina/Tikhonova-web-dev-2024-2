from flask import Flask, render_template, request, make_response
import re

app = Flask(__name__)
application = app



@app.route('/')
def index():
    url = request.url
    return render_template('index.html', url=url)

@app.route('/args')
def args():
    return render_template('args.html')

@app.route('/headers')
def headers():
    return render_template('headers.html')

@app.route('/cookies')
def cookies():
    responce = make_response(render_template('cookies.html'))
    if 'first' not in request.cookies:
        responce.set_cookie('first',"FIrsTCooKIe")
    return responce

@app.route('/form', methods=['POST','GET'])
def form():
    return render_template('form.html')

@app.route('/calc', methods=['POST','GET'])
def calc():
    res = 0
    error = ''
    if request.method=="POST":
        try:
            a, op, b = request.form['a'], request.form['operation'], request.form['b']
            match op:
                case '+':
                    res = float(a)+float(b)
                case '-':
                    res = float(a)-float(b)
                case '*':
                    res = float(a)*float(b)
                case '/':
                    res = float(a)/float(b)
        except ZeroDivisionError:
            error = 'Не дели на 0!'
        except ValueError:
            error = 'Неверный тип данных'
    return render_template('calc.html', res=res, error=error)


@app.route('/numb', methods=['POST', 'GET'])
def numb():
    error = None
    formatted_phone = ''
    phone = ''

    if request.method == 'POST':
        phone = request.form.get('phone', '')

        # Проверка формата
        if not re.match(r'^(\+7|8)?[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}$', phone) and not re.match(r'^\d{1,3}[\s.\-]?\d{1,3}[\s.\-]?\d{1,2}[\s.\-]?\d{1,2}$', phone):
            error = "Недопустимый ввод. В номере телефона встречаются недопустимые символы."
            return render_template('numb.html', error=error, phone=phone, formatted_phone=formatted_phone)
        else:
            digits = re.sub(r'\D', '', phone)
            # Проверка количества цифр
            if len(digits) not in [10, 11]:
                error = "Недопустимый ввод. Неверное количество цифр."
                return render_template('numb.html', error=error, phone=phone, formatted_phone=formatted_phone)
            else:
                # Преобразование номера телефона к формату
                formatted_phone = f"8-{digits[1:4]}-{digits[4:7]}-{digits[7:9]}-{digits[9:]}"

    return render_template('numb.html', error=error, phone=phone, formatted_phone=formatted_phone)
