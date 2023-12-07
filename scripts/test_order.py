import requests


url = "http://127.0.0.1:8000/api/order"
headers = {
    "Content-Type": "application/json",
}

# Scenario 1: Successful order
payload = {
    "payload": {
        "username": "tan",
        "quantity": 1,
        "delivery": True,
    },
    "fn": "order",
}
response = requests.post(url, json=payload, headers=headers)
print("Scenario 1: Successful order")
print(f"Status Code: {response.status_code}")
print("Response Body:")
print(response.json())
print("\n")
assert "SUCCESS" in response.json()['message']


# Scenario 2: Invalid Sufficient fund: We set that new user has 100 credits and each token cost 10 credits 
# If user req quantity is more than 10 then it should return insufficient fund
payload = {
    "payload": {
        "username": "naw(h)at",
        "quantity": 11,
        "delivery": True,
    },
    "fn": "order",
}
response = requests.post(url, json=payload, headers=headers)
print("Scenario 2: Insufficient Fund")
print(f"Status Code: {response.status_code}")
print("Response Body:")
print(response.json())
print("\n")
assert "INSUFFICIENT_FUND" in response.json()['message']


# Scenario 3: Invalid inventory amount. Check the current inventory amount in inventory service and then add user_credit to be able to purchase that token quantity
payload = {
    "payload": {
        "username": "boss",
        "quantity": 120,
        "delivery": True,
    },
    "fn": "order",
}
response = requests.post(url, json=payload, headers=headers)
print("Scenario 3: Insufficient token in Inventory")
print(f"Status Code: {response.status_code}")
print("Response Body:")
print(response.json())
print("\n")
assert "FAIL_INVENTORY" in response.json()['message']


# Scenario 4: Fail delivery
payload = {
    "payload": {
        "username": "boss",
        "quantity": 1,
        "delivery": False,
    },
    "fn": "order",
}
response = requests.post(url, json=payload, headers=headers)
print("Scenario 4: Fail Delivery")
print(f"Status Code: {response.status_code}")
print("Response Body:")
print(response.json())
print("\n")
assert "FAIL_DELIVERY" in response.json()['message']

