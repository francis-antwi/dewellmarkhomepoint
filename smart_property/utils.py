import requests
from dotenv import load_dotenv
import os

load_dotenv() 

def initialize_paystack_transaction(email, amount, reference):
    headers = {
        "Authorization": f"Bearer {os.getenv('PAYSTACK_SECRET_KEY')}",
        "Content-Type": "application/json",
    }
 
    data = {
        "email": email,
        "amount": int(amount) * 100,
        "reference": reference,
        "callback_url": f"https://yourdomain.com/paystack/verify/{reference}/"
    }

    response = requests.post("https://api.paystack.co/transaction/initialize", json=data, headers=headers)
    return response.json()
