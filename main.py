import json
import os
import requests
from flask import Flask, request
from loguru import logger
import base64
from flask_sqlalchemy import SQLAlchemy

GCAPIKEY = os.environ['izibiziMEAPIKey']  # api key from GetCourse
GCAPIKEY_INFO = os.environ['izibiziINFOAPIKey']  # api key from GetCourse
URL_ME = 'https://pikcher.getcourse.ru/pl/api/deals/'
URL_INFO = 'https://izibizi.getcourse.ru/pl/api/deals/'


logger.add("app.log", format="{time} {level} {message}", rotation="10 MB", compression="tar.gz", level="DEBUG",
           enqueue=True)
app = Flask(__name__)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:localDB@localhost/customers'
db = SQLAlchemy(app)


class Customers(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(100), nullable=False)


# функция отправки данных на Геткурс по юзерам
def postGCUser(email: str, cus: str):
    s = json.dumps({
        "user": {
            "email": email,
            "addfields": {"customer_id": cus}
        },
        "system": {
            "refresh_if_exists": 1
        },
    })
    url = 'https://pikcher.getcourse.ru/pl/api/users/'
    data = {
        'key': GCAPIKEY,
        'action': 'add',
        'params': base64.b64encode(s.encode('utf-8'))}
    p = requests.post(url, data=data)
    return p.json()


# функция отправки данных на Геткурс по заказам
def postGCOrder(email: str, amount: float, offer_code: str, KEY: str, URL: str):
    s = json.dumps({
        "user": {
            "email": email
        },
        "system": {
            "refresh_if_exists": 1,
            "return_payment_link": 1,
            "return_deal_number": 1
        },
        "deal": {
            "offer_code": offer_code,
            "quantity": 1,
            "deal_cost": amount,
            "deal_status": "in_work",
            "deal_is_paid": "1",
            "payment_type": "STRIPE",
            "payment_status": "accepted",
            "deal_currency": "USD"
        },
    })
    url = URL
    data = {
        'key': KEY,
        'action': 'add',
        'params': base64.b64encode(s.encode('utf-8'))}
    p = requests.post(url, data=data)
    return p.json()


# функция приёма вебхуков по первой онлайн школе
@logger.catch()
@app.route('/webhook_test', methods=['POST', 'GET'])
def webhook_test():
    if request.method == 'POST':
        r = request.json
        logger.info(r)
        l1 = tuple(r.get('data').get('object').get('lines').get('data'))  # переводим в кортеж
        # проверяем какой прайс
        if type(l1[0]['plan']) == dict:
            if r.get('data').get('object').get('total') == 0:
                # free for 0$
                email = r.get('data').get('object').get('customer_email')
                logger.info('trial ' + str(email))
                resp = postGCOrder(email, 0, 'FreeTrial', GCAPIKEY, URL_ME)
                logger.info('success send order to GetCourse, email: ' + str(email) + ' offer code: ' +
                            str(l1[0]['plan']['id']))
                logger.info('otvet zaprosa: ' + str(resp))
            else:
                # 9$
                email = r.get('data').get('object').get('customer_email')
                offer_code = l1[0]['plan']['id']
                amount = l1[0]['plan']['amount'] / 100
                logger.info('Платный заказ ' + str(email))
                resp = postGCOrder(email, amount, offer_code, GCAPIKEY, URL_ME)
                logger.info('success send order to GetCourse, email: ' + str(email) + ' offer code: ' + str(offer_code)
                            + ' amount: ' + str(amount))
                logger.info('otvet zaprosa: ' + str(resp))
        else:
            offer_code = l1[0]['price']['id']
            amount = l1[0]['amount'] / 100
            if amount <= 9:
                offer_code = 'Trial1$'
            email = r.get('data').get('object').get('customer_email')
            logger.info('offer code: ' + str(offer_code) + ' email: ' + str(email))
            resp = postGCOrder(email, amount, offer_code, GCAPIKEY, URL_ME)
            logger.info('success send order to GetCourse, email: ' + str(email) + ' offer code: ' +
                        str(l1[1]['plan']['id']))
            logger.info('otvet zaprosa: ' + str(resp))
        return 'success', 200, {'Content-Type': 'applicaton/json'}
    else:
        logger.info('неверный запрос ' + str(request) + 'Headers: ' + str(request.headers) + ' DATA: ' +
                    str(request.data) + 'URL: ' + str(request.url))
        json_response = {'server_status': 201, 'description': 'pls send post request', }
        return json.dumps(json_response, indent=2), 201, {'Content-Type': 'application/json'}


# функция приёма вебхуков по английской онлайн школе
@logger.catch()
@app.route('/webhook_info', methods=['POST', 'GET'])
def webhook_info():
    if request.method == 'POST':
        r = request.json
        logger.info(r)
        # переводим в кортеж чтоб было проще обрабатывать данные
        l1 = tuple(r.get('data').get('object').get('lines').get('data'))
        # проверяем какой прайс
        if type(l1[0]['plan']) == dict:
            # если содержит 2 позиции в заказе, то 1й план будет словарём
            if r.get('data').get('object').get('total') == 0:
                # если это заказ с триал периодом, то передаём "FreeTrial" как айди офера для создания заказа
                email = r.get('data').get('object').get('customer_email')
                # записываем в лог все основные действия
                logger.info('trial ' + str(email))
                # передаём заказа на геткурс с почтой, суммой заказа, оффер айди,ключ АПИ с ГК, урл ГК аккаунта
                resp = postGCOrder(email, 0, 'FreeTrial', GCAPIKEY_INFO, URL_INFO)
                logger.info('success send order to GetCourse, email: ' + str(email) + ' offer code: ' +
                            str(l1[0]['plan']['id']))
                logger.info('otvet zaprosa: ' + str(resp))
            else:
                # 9$
                email = r.get('data').get('object').get('customer_email')
                offer_code = l1[0]['plan']['id']
                amount = l1[0]['plan']['amount'] / 100
                logger.info('Платный заказ ' + str(email))
                resp = postGCOrder(email, amount, offer_code, GCAPIKEY_INFO, URL_INFO)
                logger.info('success send order to GetCourse, email: ' + str(email) + ' offer code: ' + str(offer_code)
                            + ' amount: ' + str(amount))
                logger.info('otvet zaprosa: ' + str(resp))
        else:
            offer_code = l1[0]['price']['id']
            amount = l1[0]['amount'] / 100
            if amount <= 9:
                offer_code = 'Trial1$'
            email = r.get('data').get('object').get('customer_email')
            logger.info('offer code: ' + str(offer_code) + ' email: ' + str(email))
            resp = postGCOrder(email, amount, offer_code, GCAPIKEY_INFO, URL_INFO)
            logger.info('success send order to GetCourse, email: ' + str(email) + ' offer code: ' +
                        str(l1[1]['plan']['id']))
            logger.info('otvet zaprosa: ' + str(resp))
        return 'success', 200, {'Content-Type': 'applicaton/json'}
    else:
        logger.info('неверный запрос ' + str(request) + 'Headers: ' + str(request.headers) + ' DATA: ' +
                    str(request.data) + 'URL: ' + str(request.url))
        json_response = {'server_status': 201, 'description': 'pls send post request', }
        return json.dumps(json_response, indent=2), 201, {'Content-Type': 'application/json'}


# ожидаю бизнс логику для продолжения интеграции
@logger.catch()
@app.route('/webhook_razorpay', methods=['POST', 'GET'])
def webhook_razorpay():
    if request.method == 'POST':
        r = request.json
        logger.info(r)
        if r.get('event') == 'payment.authorized':
            amount = r.get('payload').get('payment').get('entity').get('amount')
            email = r.get('payload').get('payment').get('entity').get('email')
        else:
            pass
        return 'success', 200, {'Content-Type': 'applicaton/json'}
    else:
        logger.info('неверный запрос ' + str(request) + 'Headers: ' + str(request.headers) + ' DATA: ' +
                    str(request.data) + 'URL: ' + str(request.url))
        json_response = {'server_status': 201, 'description': 'pls send post request', }
        return json.dumps(json_response, indent=2), 201, {'Content-Type': 'application/json'}


@logger.catch()
@app.route('/test')
def printHello():
    return "<p>Hello World</p>", logger.info('Hello World')


@logger.catch()
@app.route('/')
def index():
    return "<p> index page </p>", logger.info('Index page')


if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
