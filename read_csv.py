import pandas as pd

df = pd.read_csv('mapping2.csv')
filtered_df = df[df['Tag Name'].str.contains('TT_101')]
print(filtered_df)
