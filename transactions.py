import asyncio

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

    async def payBalance(self, billId, amount, comment):
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

    async def status(self, billId):
        statusUrl = self.url + billId
        request = requests.get(statusUrl, headers=self.headers)
        request = request.json()
        try:
            status = request['status']['value']
            if status:
                return status
        except KeyError:
            return 'ErrorStatus'

    async def reject(self, billId):
        rejectUrl = self.url + billId + '/reject'
        request = requests.post(rejectUrl, headers=self.headers).json()
        try:
            url = request['payUrl']
            if url:
                return url
        except KeyError:
            return 'ErrorReject'
