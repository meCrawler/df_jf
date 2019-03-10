
from core.feature import *
from core.predict import *
from core.merge_multiple_file import *

from core.check import check_options




@timed()
def merge_file(base_file = './output/0.70180553000.csv', top_n=5, fillzero=True):
    base_df = pd.read_csv(base_file)
    base_df.index = get_template_with_position().index_ex.values

    if fillzero:
        other_col = ['var053','var066','var016','var020','var047']
        logger.info(f'Set some col({len(other_col)}) to -1:{other_col}')
        base_df.loc[:, other_col] = -1

    #base_df.loc[:,:]= None
    bk_list = get_blocks()
    existing_file = get_existing_blks()
    file_sn = 0

    from core.merge_multiple_file import select_col
    select_col = select_col[:top_n]

    # other_col = [col for col in base_df.columns if col not in select_col and 'var' in col]
    # logger.info(f'Set some col({len(other_col)}) to Null:{other_col}')
    # base_df.loc[:, other_col] = None

    for blk_id, cnt in existing_file.items():
        cur_blk = bk_list.iloc[blk_id]
        wtid = cur_blk.wtid
        col_name = cur_blk.col

        if col_name not in select_col:
            logger.warning(f'{col_name} is not in the select list:{select_col}')
            continue


        file_list = glob(f'./output/blocks/{col_name}/*_{blk_id:06}_*.csv')
        file_list = sorted(file_list)

        score_all = np.zeros((cur_blk.length,cnt))

        for sn, file_path in enumerate(file_list):
            value = pd.read_csv(file_path, header=None)
            score_all[:,sn]=value.iloc[:,1].values

        base_df.loc[(base_df.wtid==wtid) &
                    (base_df.index.isin(value.iloc[:,0])), col_name]  \
            = score_all.mean(axis=1)
        file_sn += 1
        logger.info(f'Blk:{blk_id} is done, {file_sn:05}, {file_list}, {score_all.shape}')
        #print(score_all[:3])

    base_df = convert_enum(base_df)

    file = f"{base_file}_m0_{file_sn}_{top_n}_{'_'.join(select_col[:top_n])}_{int(time.time() % 10000000)}.csv"
    base_df.iloc[:, :70].to_csv(file, index=None)
    logger.info(f'Merge file save to:{file}')
    return base_df.iloc[:, :70]

@timed()
def gen_best(count_columns):
    from multiprocessing import Pool as ThreadPool

    #imp_list =  ['var042', 'var046', 'var004', 'var027', 'var034', 'var043', 'var068', 'var003', 'var052', 'var040', 'var056', 'var024']
    from core.merge_multiple_file import select_col
    imp_list = select_col[:count_columns]
    logger.info(f'There are {len(imp_list)} col need to gen_result:{imp_list}')

    from core.check import get_miss_blocks_ex

    snap = pd.read_hdf('./imp/v3.h5')

    arg_list = []
    for col_name in imp_list:

        for bin_id in range(check_options().bin_count):
            blk_list = get_miss_blocks_ex()
            blk_list = blk_list.loc[
                (blk_list.kind=='missing') &
                (blk_list.bin_id==bin_id) &
                (blk_list.col==col_name)]

            best = snap[(snap.bin_id == bin_id) & (snap.col_name == col_name)]  # get_best_arg_by_blk(bin_id, col_name, 'lr', 'down', shift=0) #gen_best
            if best is None or len(best)==0:
                logger.warning(f'Can not get arg for:bin_id:{bin_id}, {col_name}, and the block length is:{len(blk_list)}')
                continue
            else:
                best = best.iloc[0]
            for blk_id in blk_list.index:
                best = best.copy()
                best['blk_id']  =blk_id
                #TODO
                #best['col_per'] = 0.85
                arg_list.append(best)

    logger.info(f'There are {len(arg_list)} blockid need to process')
    pool = ThreadPool(10)
    pool.map(gen_best_sub, arg_list, chunksize=np.random.randint(1,64))

def get_existing_blks():
    file_list = glob('./output/blocks/*/*.csv')
    file_list = sorted(file_list)
    file_map = DefaultMunch(0)
    for file_path in file_list:
        import ntpath
        file_name = ntpath.basename(file_path)
        blk_id = int(file_name.split('_')[1])
        file_map[blk_id] = file_map[blk_id] +1
        #print(file_name.split('_')[1])
    return dict(file_map)

if __name__ == '__main__':
    """
    nohup python ./core/merge.py --col_count 4 > merge_$(hostname).log 2>&1 &
    """

    import sys

    count_columns = check_options().col_count
    gen_best(count_columns)
    merge_file(top_n=count_columns)
    #merge_diff_col()


