import requests

data = {
    "action": "chart",
    "username": "test_user",
    "chart_type": "bar",
    "data": [
        {"district_name": "Srikakulam", "total_students": 500},
        {"district_name": "Visakhapatnam", "total_students": 1200}
    ]
}

response = requests.post("http://127.0.0.1:8000/ask", json=data)
print("Status Code:", response.status_code)
if response.status_code == 200:
    res_json = response.json()
    print("Status:", res_json.get("status"))
    svg = res_json.get("svg", "")
    print("SVG generated:", len(svg) > 0)
    print(svg[:100] + "..." if svg else "No SVG returned")
else:
    print("Error:", response.text)
