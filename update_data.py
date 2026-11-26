import csv, io, pathlib, urllib.request
import yfinance as yf
p=pathlib.Path('data');p.mkdir(exist_ok=True)
for key, ticker in {'US10Y':'DGS10','VIX':'VIXCLS','DXY':'DX-Y.NYB','MOVE':'^MOVE'}.items():
    try:
        if key in ('US10Y','VIX'):
            raw=urllib.request.urlopen('https://fred.stlouisfed.org/graph/fredgraph.csv?id='+ticker,timeout=40).read().decode()
            rows=[(d,float(v)) for d,v in list(csv.reader(io.StringIO(raw)))[1:] if v not in ('','.')] 
        else:
            h=yf.Ticker(ticker).history(period='max',auto_adjust=False)
            rows=[(d.strftime('%Y-%m-%d'),float(v)) for d,v in h.Close.dropna().items()]
        if not rows: raise ValueError('Sin datos')
        with (p/(key+'.csv')).open('w') as f:
            w=csv.writer(f);w.writerow(['Date','Close']);w.writerows(rows)
    except Exception as e: print(f'{key}: {e}')
