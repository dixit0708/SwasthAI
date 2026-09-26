import pandas as pd

try:
    print("Fetching DEMO...")
    demo = pd.read_sas('https://wwwn.cdc.gov/Nchs/Nhanes/2017-2018/DEMO_J.XPT')
    print("Fetching BPX...")
    bpx = pd.read_sas('https://wwwn.cdc.gov/Nchs/Nhanes/2017-2018/BPX_J.XPT')
    print("Fetching TCHOL...")
    tchol = pd.read_sas('https://wwwn.cdc.gov/Nchs/Nhanes/2017-2018/TCHOL_J.XPT')
    print("Fetching HDL...")
    hdl = pd.read_sas('https://wwwn.cdc.gov/Nchs/Nhanes/2017-2018/HDL_J.XPT')
    print("Fetching GLU...")
    glu = pd.read_sas('https://wwwn.cdc.gov/Nchs/Nhanes/2017-2018/GLU_J.XPT')
    
    df = demo[['SEQN', 'RIDAGEYR']].merge(bpx[['SEQN', 'BPXSY1', 'BPXDI1']], on='SEQN')
    df = df.merge(tchol[['SEQN', 'LBXTC']], on='SEQN', how='left')
    df = df.merge(hdl[['SEQN', 'LBDHDD']], on='SEQN', how='left')
    df = df.merge(glu[['SEQN', 'LBXGLU']], on='SEQN', how='left')
    
    print(df.head())
    print(f"Shape: {df.shape}")
except Exception as e:
    print(f"Error: {e}")
