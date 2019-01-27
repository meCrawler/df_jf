from core.feature import *
import fire


def score(val1, val2, enum=False):
    loss = 0
    for real, predict in zip(val1, val2):
        if enum:
            loss += 1 if real == predict else 0
        else:
            loss += np.exp(-100 * abs(real - np.round(predict,2)) / max(abs(real), 1e-15))
    return len(val1), round(loss, 4)



def get_predict_fun(blockid, train):
    block = get_blocks().iloc[blockid]

    col_name = block['col']

    wtid = block['wtid']

    is_enum = True if 'int' in date_type[col_name].__name__ else False

    if is_enum:
        fn = lambda val: np.full_like(train[col_name], train[col_name].value_counts().index[0])
    else:

        from sklearn.linear_model import Ridge

        np.random.seed(0)

        clf = Ridge(alpha=100.0)
        train_X = train.iloc[:, 1:]
#         if train.shape[1] == 1:
#             train_X = np.expand_dims(train_X, axis=1)
#         print(train_X.shape)
#         print(train[col_name].shape)
        clf.fit(train_X, train[col_name])
        fn = clf.predict

    return fn

@file_cache()
def predict_wtid(wtid):
    block_list = get_blocks()

    train_ex = get_train_ex(wtid)
    for blockid, missing_block in block_list.loc[
                (block_list.wtid == wtid) & (block_list.kind == 'missing')].iterrows():
        col_name = missing_block.col
        train, sub = get_submit_feature_by_block_id(blockid)

        predict_fn = get_predict_fun(blockid, train)
        predict_res = predict_fn(sub.time_sn)
        sub[col_name] = predict_res
        logger.debug(f'predict_res:{predict_res.shape}, {type(predict_res)}')
        begin, end = missing_block.begin, missing_block.end

        logger.debug(
            f'train.loc[begin:end,col_name] = {train_ex.loc[begin:end,col_name].shape}, predict_res:{predict_res.shape}, {begin}, {end}, {wtid}, {col_name}')
        train_ex.loc[begin:end, col_name] = predict_res
        logger.debug(f'wtid:{wtid},col:{missing_block.col}, blockid:{blockid},train_ex:{train_ex.shape}, train:{train.shape}')

    submit = get_sub_template()
    submit = submit.loc[submit.wtid==wtid]
    submit.ts = pd.to_datetime(submit.ts)
    train_ex = train_ex[ train_ex.ts.isin(submit.ts) ]
    train_ex.wtid = train_ex.wtid.astype(int)
    return convert_enum(train_ex)

@file_cache()
def predict_all():

    train_list = []
    from tqdm import tqdm
    for wtid in tqdm(range(1, 34)):
        train_ex =  predict_wtid(wtid)
        #train_ex = train_ex.set_index(['ts', 'wtid'])
        train_list.append(train_ex)
    train_all = pd.concat(train_list)#.set_index(['ts', 'wtid'])
    train_all.wtid = train_all.wtid.astype(int)


    submit = get_sub_template()
    submit.ts = pd.to_datetime(submit.ts)


    submit = submit[['ts', 'wtid']].merge(train_all, how='left', on=['ts', 'wtid'])

    submit.drop(axis=['column'], columns=['time_sn'], inplace=True)

    submit = convert_enum(submit)

    submit = round(submit, 2)

    logger.debug(f'Sub file save to {file}')

    return submit


@timed()
def save_to_file(submit):
    template = get_sub_template()
    file = './output/submit_nan.csv'
    submit = submit.where(pd.isna(template))


    submit.ts = template.ts
    submit.wtid = template.wtid


    submit.to_csv(file,index=None)


@timed()
@file_cache(overwrite=False)
def check_score_all(pic=False, version='0125'):
    std = get_std_all()
    std = std.groupby(['col', 'data_type']).agg({'mean': ['mean', 'min', 'max', 'std']})
    std = std.reset_index().set_index('col')

    std['coef_wtid_avg'] = np.nan
    std['coef_wtid_max'] = np.nan
    std['coef_wtid_id'] = np.nan

    std['score_1_file'] = np.nan
    std['score_2_file'] = np.nan
    std['score_3_file'] = np.nan
    std['score_4_file'] = np.nan
    std['score_5_file'] = np.nan


    for col in get_predict_col():
        corr = get_corr_wtid(col)
        std.loc[col, 'coef_wtid_avg'] = corr.where(corr < 0.999).max().mean()
        std.loc[col, 'coef_wtid_max'] = corr.where(corr < 0.999).max().max()
        std.loc[col, 'coef_wtid_id'] = corr.where(corr < 0.999).max().idxmax()

        for file_num in range(1, 6):
            loss = check_score(col, pic, file_num)
            std.loc[col, f'score_{file_num}_file'] = loss

    return std.sort_values('score_1_file')


def check_score(col, pic, file_num):
    args = locals()
    logging.getLogger().setLevel(logging.INFO)
    import matplotlib.pyplot as plt

    train_list = get_train_feature(3, col, file_num)

    train_list = sorted(train_list, key=lambda val: len(val[1]), reverse=True)

    count, loss = 0, 0

    if pic ==True:
        train_list = train_list[:10]
    for train, val, blockid in train_list :

        is_enum = True if 'int' in date_type[col].__name__ else False

        fn = get_predict_fun(blockid, train)

        if pic:
            plt.figure(figsize=(20, 5))
            for color, data in zip(['#ff7f0e', '#2ca02c'], [train, val]):
                plt.scatter(data.time_sn, data[col], c=color)

            x = np.linspace(train.time_sn.min(), train.time_sn.max(), 10000)
            plt.plot(x, fn(x))
            plt.show()

        val_res = fn(train.iloc[:, 1:])
        logger.debug(f'shape of predict output {val_res.shape}, with paras:{args}')
        cur_count, cur_loss = score(val[col], val_res, is_enum)

        loss += cur_loss
        count += cur_count
        avg_loss = round(loss/count, 4)
        logger.debug(f'blockid:{blockid}, {train.shape}, {val.shape}, score={round(cur_loss/cur_count,3)}')
    logger.info(f'Total loss:{avg_loss:.4f}, is_enum:{is_enum}, col:{col}: ')

    return avg_loss





if __name__ == '__main__':
    """
    python core/train.py predict_wtid 1

    """
    #logging.getLogger().setLevel(logging.INFO)
    #fire.Fire()

    score_df = check_score_all(version='0126')





