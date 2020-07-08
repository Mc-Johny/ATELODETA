import asyncio
import time

import requests
import json
import datetime as dt
import config


class Qiwi:
    def __init__(self):
        self.url = 'https://api.qiwi.com/partner/bill/v1/bills/'
        self.headers = {
            'Accept': 'application/json',
            'Content-type': 'application/json',
            'Authorization': 'Bearer ' + config.private_token
        }

    async def dateLifetime(self):
        date = dt.datetime.now() + dt.timedelta(days=15)
        return dt.datetime.strftime(date, '%Y-%m-%dT%H:%M:%S') + '+04:00'

    async def payBalance(self, billId: str, amount: int, comment: str):
        paymentUrl = self.url + billId
        amount = amount + 0.01
        params = {
            "amount": {
                "currency": "RUB",
                "value": amount
            },
            "comment": comment,
            "expirationDateTime": await self.dateLifetime()
        }
        params = json.dumps(params)
        request = requests.put(paymentUrl, headers=self.headers, data=params)
        request = request.json()
        try:
            url = request['payUrl']
            if url:
                return url
        except Exception:
            return 'ErrorPay'

    async def status(self, billId: str):
        statusUrl = self.url + billId
        request = requests.get(statusUrl, headers=self.headers)
        request = request.json()
        try:
            status = request['status']['value']
            if status:
                return status
        except KeyError:
            return 'ErrorStatus'

    async def reject(self, billId: str):
        rejectUrl = self.url + billId + '/reject'
        request = requests.post(rejectUrl, headers=self.headers).json()
        try:
            url = request['payUrl']
            if url:
                return url
        except KeyError:
            return 'ErrorReject'

    async def moneyTransfer(self, amount: int, qiwiNumber: str, comment: str):
        session = requests.Session()
        session.headers = {'content-type': 'application/json'}
        session.headers['authorization'] = 'Bearer ' + config.qiwi_token
        session.headers['User-Agent'] = 'Android v3.2.0 MKT'
        session.headers['Accept'] = 'application/json'
        postjson = {"id": str(int(time.time()) * 1000), "sum": {
            "amount": amount,
            "currency": '643'
        }, "paymentMethod": {
            "type": "Account",
            "accountId": "643"
        }, "comment": comment, "fields": {
            "account": qiwiNumber
        }}
        params = json.dumps(postjson)
        response = session.post('https://edge.qiwi.com/sinap/api/v2/terms/99/payments', data=params)
        return response.json()
