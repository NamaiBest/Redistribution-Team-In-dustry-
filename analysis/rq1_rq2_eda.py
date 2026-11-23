"""EDA, RQ1 and RQ2 on the full FreshRetailNet-50K training set.

Run from the repo root with train.parquet in the working directory (see run_analysis.py for the download).
"""
import numpy as np, pandas as pd, pyarrow.parquet as pq, json
import statsmodels.api as sm
f=pq.ParquetFile('train.parquet')
S=np.zeros(24);I=np.zeros(24);C=np.zeros(24);O=np.zeros(24);n=0
for g in range(f.num_row_groups):
    t=f.read_row_group(g,columns=['hours_sale','hours_stock_status']); k=t.num_rows
    hs=t.column('hours_sale').combine_chunks().flatten().to_numpy().reshape(k,24)
    st=t.column('hours_stock_status').combine_chunks().flatten().to_numpy().reshape(k,24)
    S+=hs.sum(0); ins=st==0; I+=(hs*ins).sum(0); C+=ins.sum(0); O+=st.sum(0); n+=k
overall=S/n; instock=I/C; out_rate=O/n
gap=(instock-overall)/overall
day=slice(6,22)
r1=dict(peak_hour=int(np.argmax(overall)),peak_val=round(overall.max(),4),
        afternoon={h:round(overall[h],4) for h in range(13,18)},
        stockout_rate={h:round(out_rate[h],4) for h in [6,9,12,15,18,21,22,23]},
        daytime_stockout_avg=round(out_rate[day].mean(),4),
        max_daytime_gap_pct=round(100*gap[day].max(),2),gap_hour=int(6+np.argmax(gap[day])),
        overall_hourly=[round(x,4) for x in overall])
cols=['sale_amount','stock_hour6_22_cnt','discount','activity_flag','store_id','product_id']
d=pq.read_table('train.parquet',columns=cols).to_pandas()
eda=dict(rows=len(d),mean=round(d.sale_amount.mean(),3),median=round(d.sale_amount.median(),3),
  mean_stockout_h=round(d.stock_hour6_22_cnt.mean(),2),activity_share=round(d.activity_flag.mean(),4),
  tiers={'full':round((d.discount>=1).mean(),4),'light':round(((d.discount>=0.86)&(d.discount<1)).mean(),4),
         'moderate':round(((d.discount>0.70)&(d.discount<0.86)).mean(),4),'deep':round((d.discount<=0.70).mean(),4)},
  campaign_disc_share=round((d[d.activity_flag==1].discount<1).mean(),4),
  disc_campaign=round(d[d.activity_flag==1].discount.mean(),4),disc_non=round(d[d.activity_flag==0].discount.mean(),4))
# quartile tiers by zero-stockout median per series, decay by stockout bucket
key=d.store_id.astype(np.int64)*10000+d.product_id.astype(np.int64); d['key']=key
base=d[d.stock_hour6_22_cnt==0].groupby('key').sale_amount.median()
d['tier']=d.key.map(pd.qcut(base,4,labels=['Q1','Q2','Q3','Q4']))
d['bucket']=pd.cut(d.stock_hour6_22_cnt,[-1,0,3,8,15,16],labels=['0h','1-3h','4-8h','9-15h','16h'])
q4=d[d.tier=='Q4'].groupby('bucket',observed=True).sale_amount.mean().round(4).to_dict()
# RQ2
deep=d[d.discount<=0.70].sale_amount.mean(); full=d[d.discount>=1].sale_amount.mean()
p=d[(d.sale_amount>0)&(d.discount>0)]
X=sm.add_constant(pd.DataFrame({'ln_disc':np.log(p.discount),'activity':p.activity_flag,'stock_h':p.stock_hour6_22_cnt}).astype(float))
m=sm.OLS(np.log(p.sale_amount.astype(float)),X).fit(cov_type='cluster',cov_kwds={'groups':p.key.values})
ci=m.conf_int().loc['ln_disc']
r2=dict(deep=round(deep,4),full=round(full,4),ratio=round(deep/full,2),elast=round(m.params.ln_disc,4),ci=[round(ci[0],3),round(ci[1],3)],
        activity=round(m.params.activity,4),act_pct=round(100*(np.exp(m.params.activity)-1),2),stock=round(m.params.stock_h,4),r2=round(m.rsquared,4),n=len(p))
json.dump(dict(eda=eda,rq1=r1,q4=q4,rq2=r2),open('analysis/rq1_rq2_eda.json','w'),indent=1,default=float)
print(json.dumps(dict(eda=eda,rq1={k:v for k,v in r1.items() if k!='overall_hourly'},q4=q4,rq2=r2),indent=1,default=float))
