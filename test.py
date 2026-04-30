import json
j_str = "{'月／日': {'name': 'itemDate', 'value': '2023-07-24', 'type': 'date'}, '区分': {'type': 'select', 'name': 'division', 'multiple': False, 'value': '運賃', 'text': '運賃'}, '金額': {'name': 'lineCharge', 'value': '1000', 'type': 'number'}, '支払先名': {'error': '支払先名の入力が必要です!', 'name': 'payee', 'value': '', 'type': 'text'}, '項目': {'name': 'content', 'value': '', 'type': 'text'}, '駅from': {'name': 'stationf', 'value': '新大久保', 'type': 'text'}, '駅to': {'name': 'stationt', 'value': '国立', 'type': 'text'}, '社用カード利用': {'name': 'lineUseCard', 'value': 'true', 'type': 'checkbox', 'checked': 'checked'}, '_csrf': {'name': '_csrf', 'value': '34e215e8-79c6-4a2c-a8d3-ab8f07e8fde6', 'type': 'hidden'}, 'id': {'name': 'id', 'value': '65', 'type': 'hidden'}}"
j_str = j_str.replace("'", '"').replace("True", "true").replace("False", "false")
fields = json.loads(j_str)
error_keys = [k for k,v in fields.items() if isinstance(v, dict) and v.get("error")]
error_detail =  f"{error_keys[0]} : {fields[error_keys[0]].get('error')}"
print(error_detail)