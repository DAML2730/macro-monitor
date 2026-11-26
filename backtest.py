import pandas as pd, numpy as np, yfinance as yf, subprocess,json,pathlib
from io import StringIO
import urllib.request
P=pathlib.Path('backtest-results');P.mkdir(exist_ok=True)
series={}
for k,t in {'DFII10':'DFII10','US10Y':'DGS10','T10YIE':'T10YIE','VIX':'VIXCLS','DXY':'DX-Y.NYB','MOVE':'^MOVE'}.items():
    if k in ['DXY','MOVE']:
        s=yf.Ticker(t).history(period='max',auto_adjust=False).Close
    else:
        d=pd.read_csv(StringIO(urllib.request.urlopen('https://fred.stlouisfed.org/graph/fredgraph.csv?id='+t,timeout=60).read().decode()));s=pd.Series(pd.to_numeric(d.iloc[:,1],errors='coerce').values,index=pd.to_datetime(d.iloc[:,0]))
    s=s.dropna().sort_index(); assert len(s)>1000,k
    series[k]=[{'date':str(d.date()),'value':float(v)} for d,v in s.items()]
js="const e=require('./engine.js');let s='';process.stdin.on('data',x=>s+=x);process.stdin.on('end',()=>console.log(JSON.stringify(e.run(JSON.parse(s),new Date().toISOString().slice(0,10)))));"
h=pd.DataFrame(json.loads(subprocess.check_output(['node','-e',js],input=json.dumps(series).encode()))); assert len(h)>100,'Insufficient common history'; h['date']=pd.to_datetime(h.date);h.drop(columns='parts').to_csv(P/'signals.csv',index=False)
keys=['DFII10','DXY','US10Y','MOVE','VIX','T10YIE']; parts=np.array([[p['score'] for p in row] for row in h.parts]); results=[]; alerts=[]
for ticker in ['BTC-USD','GLD','SPY','QQQ','SMH']:
    a=yf.Ticker(ticker).history(period='max',auto_adjust=True); a.index=a.index.tz_localize(None); a=a.sort_index(); a=a.loc[a.index>=h.date.min()+pd.Timedelta(days=4)]; assert len(a)>100,ticker
    for model,w in [('beta',[25,25,5,20,20,5]),('equal',[100/6]*6),('no_redundancy',[30,30,0,20,20,0])]:
        score=parts@np.array(w)/100; sig=pd.DataFrame({'date':h.date,'score':score}); sig['entry']=(sig.score>=55)&(sig.score.shift()<55);sig['exit']=(sig.score<=45)&(sig.score.shift()>45); sig['available']=sig.date+pd.Timedelta(days=4)
        # conservative Tuesday or later open; latest vintage FRED, not point-in-time
       daily=pd.merge_asof(pd.DataFrame({'date':a.index.astype('datetime64[ns]')}),sig[['available','score']].astype({'available':'datetime64[ns]'}),left_on='date',right_on='available',direction='backward'); daily.index=a.index
        state=0; pos=[]
        for v in daily.score:
            if v>=55:state=1
            elif v<=45:state=0
            pos.append(state)
        r=a.Open.shift(-1)/a.Open-1; r=r.iloc[:-1]; p=pd.Series(pos,index=a.index).iloc[:-1]; strat=p*r-p.diff().abs().fillna(p.iloc[0])*.001
        for label,ret in [(model,strat),('hold',r)]:
            if label=='hold' and model!='beta':continue
            for period,rr in [('all',ret),('last_25pct',ret.iloc[int(len(ret)*.75):])]:
                equity=(1+rr).cumprod(); years=(rr.index[-1]-rr.index[0]).days/365.25; dd=(equity/equity.cummax()-1).min(); results.append(dict(asset=ticker,model=label,period=period,start=str(rr.index[0].date()),end=str(rr.index[-1].date()),CAGR=equity.iloc[-1]**(1/years)-1,max_drawdown=dd,sharpe=rr.mean()/rr.std()*np.sqrt(len(rr)/years) if rr.std() else np.nan))
        for _,s in sig[sig.entry|sig.exit].iterrows():
            i=a.index.searchsorted(s.available)
            if i>=len(a):continue
            row={'asset':ticker,'model':model,'signal':'entry' if s.entry else 'exit','date':str(a.index[i].date())}
            for weeks in [1,4,12,26]:
                j=a.index.searchsorted(a.index[i]+pd.Timedelta(weeks=weeks));row[f'return_{weeks}w']=a.Open.iloc[j]/a.Open.iloc[i]-1 if j<len(a) else np.nan
            alerts.append(row)
pd.DataFrame(results).to_csv(P/'metrics.csv',index=False);pd.DataFrame(alerts).to_csv(P/'alerts.csv',index=False)
