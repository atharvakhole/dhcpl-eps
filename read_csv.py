import pandas as pd

df = pd.read_csv('mapping2.csv')
filtered_df = df[df['Tag Name'].str.contains('RCT_RX03')]
print(filtered_df)
