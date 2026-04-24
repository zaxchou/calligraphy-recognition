import pandas as pd
df = pd.read_csv(r'E:\李鱓全集\修改版\匹配表_2026-04-15.csv', encoding='utf-8-sig')
pd.set_option('display.max_rows', None)
pd.set_option('display.max_colwidth', 60)
pd.set_option('display.width', 200)
print(df[['源文件名','匹配方式','匹配页码','pHash距离','新文件名']].to_string(index=False))
