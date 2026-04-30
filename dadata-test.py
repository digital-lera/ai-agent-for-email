from dadata import Dadata
token = "e0d228f05b80000f2c49189aa9b2c6082d6c062f"
dadata = Dadata(token)
result = dadata.find_by_id("party", "1655268265")

print(result)
