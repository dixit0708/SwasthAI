import requests
import pandas as pd
import io

def get_xpt(url):
    headers = {'User-Agent': 'Mozilla/5.0'}
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        return pd.read_sas(io.BytesIO(r.content), format='xport')
    else:
        raise Exception(f"Failed: {r.status_code}")

try:
    print("Fetching DEMO...")
    demo = get_xpt('https://wwwn.cdc.gov/Nchs/Nhanes/2017-2018/DEMO_J.XPT')
    print("Demo shape:", demo.shape)
except Exception as e:
    print(e)
