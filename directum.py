import requests
import datetime

DIRECTUM_URL = "https://directumrx-test.uktaif.ru/Integration/odata/"

now = datetime.datetime.now()

AUTH = ("StryginaVM","SwkRE4PrSwkRE4P")

doc_response = requests.get(
        f"{DIRECTUM_URL}$metadata",
        auth=AUTH,
        verify=False
        )
with open("output.txt","w") as f:
    f.write(doc_response.content.decode('utf-8'))
#doc_response = requests.post(
 #       f"{DIRECTUM_URL}/IIncomingLetters",
  #      json={
   #         "Name":"test",
    #        "Subject":"test",
     #      "Correspondent@odata.bind":f"{DIRECTUM_URL}/ICounterparties(2265)"
      #      
       #     },
        #       auth=AUTH,
        #
        #verify=False
#)


print(doc_response)
