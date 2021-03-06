import mysql.connector
import mysqlx
from core.feature import *
from file_cache.utils.util_log import timed




import contextlib


version = 3
@contextlib.contextmanager
def named_lock(db_session, name, timeout):
    """Get a named mysql lock on a DB session
    """
    lock = db_session.execute("SELECT GET_LOCK(:lock_name, :timeout)",
                              {"lock_name": name, "timeout": timeout}).scalar()
    if lock:
        try:
            yield db_session
        finally:
            db_session.execute("SELECT RELEASE_LOCK(:name)", {"name": name})
    else:
        e = "Could not obtain named lock {} within {} seconds".format(
            name, timeout)
        raise RuntimeError(e)

def get_connect():
    db = mysql.connector.connect(user='ai_lab', password=mysql_pass,
                                 host='vm-ai-2',
                                 database='ai')
    return db

def get_session():
    session = mysqlx.get_session({
        'host': 'vm-ai-2.cisco.com',
        #'port': 3306,
        'user': 'ai_lab',
        'password': mysql_pass,
        'schema': 'ai'
    })

    return session

@timed()
def check_last_time_by_binid(bin_id,col_name, threshold):
    db = get_connect()

    sql = f""" select IFNULL(max(ct),date'2011-01-01')  from score_list 
    where version={version}
    and bin_id = {int(bin_id)}
    and col_name='{col_name}'
    """
    cur = db.cursor()
    cur.execute(sql)

    latest =  cur.fetchone()[0]

    gap = (pd.to_datetime('now') - latest) / timedelta(minutes=1)

    return gap > threshold


@timed()
def check_last_time_by_wtid(key):
    db = get_connect()
    sql = f""" select IFNULL(max(mt),date'2011-01-01')  from score_list where 
    version={version} and  wtid = {int(key)}"""
    # logger.info(sql)
    cur = db.cursor()
    res = cur.execute(sql)
    return cur.fetchone()[0]



def insert(score_ind):
    score_ind = score_ind.fillna(0)
    db = get_connect()

    cur_blk = get_blocks().iloc[score_ind.blk_id]

    score_ind['length'] = cur_blk.length
    import socket
    host_name = socket.gethostname()
    score_ind['server'] = host_name
    score_ind['time_begin'] = cur_blk.time_begin
    score_ind['time_end'] = cur_blk.time_end
    score_ind = dict(score_ind )

    sql = """insert into score_list(
            blk_id  ,
            bin_id,
            wtid,
            class_name	 ,
            col_name	 ,
            direct	 ,
            file_num	 ,
            momenta_col_length	 ,
            momenta_impact	 ,
            drop_threshold	 ,
            related_col_count	 ,
            col_per,
            score	 ,
            score_count	 ,
            score_total	 ,
            time_sn	 ,
            window  ,
            n_estimators,
            max_depth,
            length ,
            shift,
            time_begin,
            time_end,
            server,
            version)
                values
                (
            {blk_id}  ,
            {bin_id},
            {wtid},
            '{class_name}'	 ,
            '{col_name}'	 ,
            '{direct}',
            {file_num}	 ,
            {momenta_col_length}	 ,
            {momenta_impact}	 ,
            round({drop_threshold},2)		 ,
            {related_col_count}	 ,
            {col_per},
            {score}	 ,
            {score_count}	 ,
            {score_total}	 ,
            {time_sn}	 ,
            round({window},2)	  ,
            {n_estimators},
            {max_depth},
            {length},
            {shift},
            {time_begin},
            {time_end},
            '{server}',
            {version}
               )
                """.format(**score_ind, version=version)
    cur = db.cursor()
    logger.debug(sql)
    cur.execute(sql )
    db.commit()




@timed()
def update(score_ind):
    score_ind = score_ind.fillna(0)
    db = get_connect()

    cur_blk = get_blocks().iloc[score_ind.blk_id]

    score_ind['length'] = cur_blk.length
    import socket
    host_name = socket.gethostname()
    score_ind['server'] = host_name
    score_ind['time_begin'] = cur_blk.time_begin
    score_ind['time_end'] = cur_blk.time_end
    score_ind = dict(score_ind )

    sql = """update score_list 
        set score_val = {score}	,
            server  =  '{server}',
            mt = now()
        where 
                blk_id =  {blk_id} and
                bin_id = {bin_id} and
                wtid = {wtid} and
                class_name	= '{class_name}' and
                col_name	= '{col_name}' and
                file_num =	  {file_num} and
                momenta_col_length	= {momenta_col_length} and
                momenta_impact	={momenta_impact}	  and
                drop_threshold	= round({drop_threshold},2) and
                related_col_count=	{related_col_count}  and
                col_per={col_per} and
                time_sn	= {time_sn}	and
                window = round({window},2)  and
                n_estimators={n_estimators} and
                max_depth={max_depth} and
                length = {length} and
                shift={shift}
                """.format(**score_ind, version=version)
    cur = db.cursor()
    logger.debug(sql)
    cur.execute(sql )
    db.commit()


def get_args_existing_by_blk(bin_id, col_name, class_name=None, direct=None, shift=0, version_loc=None):
    db = get_connect()
    class_name = 'null' if class_name is None else f"'{class_name}'"
    direct = 'null' if direct is None else f"'{direct}'"
    sql = f""" select class_name, 
                        col_name,
                        drop_threshold,
                        file_num,
                        momenta_col_length,
                        momenta_impact,
                        related_col_count,
                        col_per,
                        time_sn,
                        window,
                        n_estimators,
                        max_depth,
                        bin_id,
                        sum(score_total)/sum(score_count) score_mean,
                        sum(score_val * length)/sum(score_count) score_val_mean,
                        sum(case when score_val is Null then 1 else 0 end) zero_count,
                        std(score) score_std,
                        count(*) count_rec,
                        count(distinct blk_id) count_blk
                    from score_list where bin_id={bin_id} 
                                and col_name='{col_name}'
                                and class_name=ifnull({class_name}, class_name)
                                and direct=ifnull({direct}, direct)  
                                and version={version_loc or version}
                                and shift={shift}
                        group by
                        class_name, 
                        col_name,
                        drop_threshold,
                        file_num,
                        momenta_col_length,
                        momenta_impact,
                        related_col_count,
                        col_per,
                        time_sn,
                        window,
                        n_estimators,
                        max_depth,
                        bin_id   
                """
    logger.debug(f'get_args_existing_by_blk:{sql}')
    exist_df = pd.read_sql(sql, db)
    if len(exist_df) == 0 :
        return exist_df
    exist_df = exist_df.sort_values('score_mean', ascending=False)
    return exist_df

def get_best_arg_by_blk(bin_id,col_name, class_name=None,direct=None, top=1, shift=0, version=version, vali=False):
    args = get_args_existing_by_blk(bin_id, col_name, class_name,direct, shift, version)
    if args is not None and len(args)>1:
        count_blk_mean = args.count_blk.mean()
        # Filter exception record, such as kill
        args = args.loc[args.count_blk >= count_blk_mean]

        args['total'] = args['score_val_mean'] + args['score_mean']

        args = args.reset_index().sort_values([ 'total', 'score_val_mean','score_mean', 'file_num', 'window', 'momenta_impact', 'score_std'],
                                              ascending=[False, False, False,True, True, True,True])#.head(10)
        #args = args.sort_values('score_std')
        args['bin_id']=bin_id
        args['cnt_blk_max'] = args.count_blk.max()
        if vali:
            val_count = len(args.loc[args.zero_count == 0])
            #print(args.columns)
            if val_count < 500:
                #Some block can not find train set
                args = args.loc[args.zero_count > 2]
                args = args.drop_duplicates(['score_mean', 'score_std'])
            else:
                logger.info(f'get_best_arg_by_blk, already have {val_count} record for {bin_id}, {col_name}')
                return None
        return args.iloc[:top]
    else:
        return None

@timed()
def get_args_missing_by_blk(original: pd.DataFrame, bin_id, col_name, shift):
    original['file_num'] = original['file_num'].astype(int)
    original['momenta_col_length'] = original['momenta_col_length'].astype(int)
    original['related_col_count'] = original['related_col_count'].astype(int)
    original['time_sn'] = original['time_sn'].astype(int)

    original['n_estimators'] = original['n_estimators'].astype(int)
    original['max_depth'] = original['max_depth'].astype(int)

    original['momenta_impact'] = np.round(original['momenta_impact'], 3)
    original['drop_threshold'] = np.round(original['drop_threshold'], 3)
    original['window'] = np.round(original['window'], 3)


    exist_df = get_args_existing_by_blk(bin_id,col_name, shift=shift)

    threshold = 0.99
    if exist_df is not None and len(exist_df) > 0 and exist_df.score_mean.max() >= threshold:
        max_score = exist_df.score_mean.max()
        logger.info(f'bin_id:{bin_id}, col:{exist_df.at[1, "col_name"]}, already the socre:{round(max_score,4)}')
        return exist_df.loc[pd.isna(exist_df.index)]

    original = original.copy().drop(axis='column' ,
                                    columns=['score_mean', 'score_std',
                                             'bin_id', 'count_blk', 'count_rec',
                                             'length_max', 'score_count',
                                             'score_val_mean', 'zero_count',],errors='ignore' )

    #Can not remove time_sn, if only 1 file
    original.loc[(original.file_num == 1) & (original.time_sn == 0), 'time_sn'] = 1
    original = original.drop_duplicates(model_paras)

    if len(exist_df) == 0 :
        return original
    todo = pd.merge(original, exist_df, how='left', on=model_paras)
    # logger.info(f'{todo.shape}, {todo.columns}')
    # logger.info(f'{original.shape}, {original.columns}')
    # logger.info(f'{exist_df.shape}, {exist_df.columns}')

    todo = todo.loc[pd.isna(todo.score_mean)]
    logger.info(f'todo:{len(todo)},miss:{len(original)}, existing:{len(exist_df)}')
    return todo[original.columns].drop_duplicates(model_paras)

def get_existing_blk():
    db = get_connect()
    sql = f""" select distinct blk_id from score_list where version = {version} order by blk_id"""
    return pd.read_sql(sql, db).iloc[:,0]