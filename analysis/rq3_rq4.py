"""RQ3 and RQ4 co-occurrence with the corrected methods.

No DEA; stockout hours left out of the MLR; store-product clustered errors;
categories ranked by total sales; all store-days in the co-occurrence denominator.
"""
import numpy as np, pandas as pd, pyarrow.parquet as pq, json
import statsmodels.api as sm
cols=['city_id','store_id','management_group_id','first_category_id','product_id','dt','sale_amount','stock_hour6_22_cnt','discount','holiday_flag','activity_flag','precpt','avg_temperature','avg_humidity','avg_wind_level']
d=pq.read_table('train.parquet',columns=cols).to_pandas()
d['dt']=pd.to_datetime(d.dt); d['weekend']=(d.dt.dt.dayofweek>=5).astype(int)
out={}
print('rows',len(d),'firstcat',d.first_category_id.nunique())
# RQ3 chi-square holiday vs any stockout
from scipy.stats import chi2_contingency
ct=pd.crosstab(d.holiday_flag,d.stock_hour6_22_cnt>0); chi,p,_,_=chi2_contingency(ct); V=np.sqrt(chi/len(d))
out['chi2']=dict(chi2=round(chi,2),p=float(p),V=round(V,4))
# MLR without stockout hours, store-product clustered SE
X=sm.add_constant(d[['weekend','holiday_flag','precpt','avg_temperature','avg_humidity','avg_wind_level']].astype(float))
grp=(d.store_id.astype(np.int64)*10000+d.product_id.astype(np.int64)).values
m=sm.OLS(d.sale_amount.astype(float),X).fit(cov_type='cluster',cov_kwds={'groups':grp})
out['mlr']=dict(r2=round(m.rsquared,4),coef={k:round(v,4) for k,v in m.params.items()},t={k:round(v,2) for k,v in m.tvalues.items()},p={k:float(v) for k,v in m.pvalues.items()})
# with store-product fixed effects (demeaned) for robustness on weekend/holiday
# group comparison
g=d.groupby('management_group_id').agg(obs=('sale_amount','size'),mean_sales=('sale_amount','mean'),median_sales=('sale_amount','median'),mean_stockout_hours=('stock_hour6_22_cnt','mean'),stockout_incidence=('stock_hour6_22_cnt',lambda x:(x>0).mean()))
out['groups']=g.round(4).reset_index().to_dict('records')
# RQ4 categories by aggregate sales, store-day co-occurrence over ALL store-days
cs=d.groupby('first_category_id').sale_amount.sum().sort_values(ascending=False); top=list(cs.index[:8])
sd=d[d.first_category_id.isin(top)].groupby(['store_id','dt','first_category_id']).sale_amount.sum().unstack(fill_value=0)>0
allsd=d.groupby(['store_id','dt']).size().index
sd=sd.reindex(allsd,fill_value=False)
N=len(sd); sup={c:sd[c].mean() for c in top}
rules=[]
for i,a in enumerate(top):
  for b in top[i+1:]:
    s=(sd[a]&sd[b]).mean()
    if s<0.05: continue
    for x,y in [(a,b),(b,a)]:
      rules.append(dict(antecedent=int(x),consequent=int(y),support=round(s,4),confidence=round(s/sup[x],4),lift=round(s/(sup[x]*sup[y]),4)))
r=pd.DataFrame(rules).sort_values('lift',ascending=False)
out['store_days']=N; out['top_categories']=[int(c) for c in top]; out['cat_support']={int(k):round(v,4) for k,v in sup.items()}
out['rules_top']=r.head(10).to_dict('records'); out['n_rules']=len(r)
cx=d[d.first_category_id.isin(top)].groupby('first_category_id').agg(total_sales=('sale_amount','sum'),mean_sales=('sale_amount','mean'),mean_stockout_hours=('stock_hour6_22_cnt','mean'),stockout_incidence=('stock_hour6_22_cnt',lambda x:(x>0).mean()),mean_discount=('discount','mean')).loc[top]
out['cat_exposure']=cx.round(4).reset_index().to_dict('records')
# degree: which category appears most in high-lift rules
json.dump(out,open('analysis/rq3_rq4.json','w'),indent=1,default=float)
print(json.dumps(out,indent=1,default=float)[:6000])
