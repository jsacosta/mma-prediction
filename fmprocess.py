import pandas as pd
import numpy as np
import networkx as nx
import pickle,copy,random,fmcrawler_sql,sqlite3


from scipy.sparse import csc_matrix

def page_rank(G, s = .85, maxerr = .001):
    """
    Computes the pagerank for each of the n states.
    Used in webpage ranking and text summarization using unweighted
    or weighted transitions respectively.
    Args
    ----------
    G: matrix representing state transitions
       Gij can be a boolean or non negative real number representing the
       transition weight from state i to j.
    Kwargs
    ----------
    s: probability of following a transition. 1-s probability of teleporting
       to another state. Defaults to 0.85
    maxerr: if the sum of pageranks between iterations is bellow this we will
            have converged. Defaults to 0.001
    
    Attribution note: Not written by sh
    """
    n = G.shape[0]

    # transform G into markov matrix M
    M = csc_matrix(G,dtype=np.float)
    rsums = np.array(M.sum(1))[:,0]
    ri, ci = M.nonzero()
    M.data /= rsums[ri]

    # bool array of sink states
    sink = rsums==0

    # Compute pagerank r until we converge
    ro, r = np.zeros(n), np.ones(n)
    while np.sum(np.abs(r-ro)) > maxerr:
        ro = r.copy()
        # calculate each pagerank at a time
        for i in xrange(0,n):
            # inlinks of state i
            Ii = np.array(M[:,i].todense())[:,0]
            # account for sink states
            Si = sink / float(n)
            # account for teleportation to state i
            Ti = np.ones(n) / float(n)

            r[i] = ro.dot( Ii*s + Si*s + Ti*(1-s) )

    # return normalized pagerank
    return r/sum(r)


def create_fight_matrix(fights):
    '''
    Creates a fight adjacency matrix, where each row/column corresponds 
    to a fighter. The winner is always the column fighter, such that
    entry fight_matrix[i,j]=1 means that fighter j won over fighter i.
    
    Parameters
    ----------
    fights : dict
	     Scraped fights dict through using fmcrawler. This will be
	     saved in fighters.pickle.
    
    Returns
    -------
    fight_matrix : pd.DataFrame
    	     NxN matrix where N is the number of fighters. 
    '''

    fighters = []
    for fight in fights:
        fighters.extend(fight['Fighters'])
    

    fighters = np.unique(fighters)

    # init matrix as DataFrame
    fight_matrix = pd.DataFrame(np.zeros([len(fighters),len(fighters)]),index=fighters,columns=fighters)

    # iterate over all fights and fill in appropriate entry
    for fight in fights:
        fighter1=fight['Fighters'][0]
        fighter2=fight['Fighters'][1]
        
        if fight['Result'] == fighter1:
            col=fighter1
            row=fighter2
        elif fight['Result'] == fighter2:            
            col=fighter2
            row=fighter1

        fight_matrix.loc[row,col] = 1.0

    return fight_matrix

def create_fight_graph(fights):
    '''
    Creates a NetworkX fight graph, where each node is a fighter and
    each directed edge corresponds to a result. A node pointing
    from node i to node j means that fighter j won over fighter i.
    
    Parameters
    ----------
    fights : dict OR pd.DataFrame
	     Scraped fights dict through using fmcrawler. This will be
	     saved in fighters.pickle.
    	     OR
	     fight_matrix returned from calling create_fight_matrix.
    
    Returns
    -------
    G : nx.DiGraph
             NetworkX graph with N nodes, and K edges, corresponding
    	     to the number of fighters and fighths, respectively.
    '''

    # This lets you pass either a fights list or a fight_matrix
    if type(fights) == list:
        fight_matrix = create_fight_matrix(fights)
    elif type(fights) == pd.core.frame.DataFrame:
        fight_matrix = fights
    
    # init graph and add nodes
    G = nx.DiGraph()
    nodes = fight_matrix.columns
    G.add_nodes_from(nodes)    

    i,j = np.where(fight_matrix==1.0) # find indices for edges

    edges = [(nodes[i[k]],nodes[j[k]]) for k in range(len(i))] #add edges
    G.add_edges_from(edges)

    return G


def prune_graph(G,base_node,K):
    '''
    Takes an existing fight graph and a base node and prunes all nodes 
    which are either not connected to the base node or whose shortest
    path to the base_node is longer than K.
    
    Parameters
    ----------
    G : nx.DiGraph
	    Fight graph, e.g. created using create_fight_graph. 
    base_node : str, int
    	    Name of the base node in the network.
    K : int
            Integer value specifying the shortest path threshold.

    Returns
    -------
    G : nx.DiGraph
            Pruned network graph    	
    '''

    G = G.copy()
    if G.is_directed():
        G_un = G.to_undirected()
    else:
        G_un = G

    for node in G_un.nodes():
        if nx.has_path(G,base_node,node):
            L = nx.shortest_path_length(G,base_node,node)
        else:
            L = np.inf

        if L > K:
            G.remove_node(node)
    
    return G

def compute_graph_metrics(G,base_node):
    A = nx.adjacency_matrix(G)
    PR = page_rank(A)

    return PR
    

"""
def process_fight(fight):
    '''
    Takes a fighter-centred fight dict, obtained by crawling 
    Fightmetric and converts it into a fighter-neutral dict.
    The field 'Result' now contain the winner.
    
    Parameters
    ----------
    fight : dict
    	    fight dict obtained from crawling Fightmetric
    
    Returns
    -------
    new_fight : dict
    	    fight dict with a fight-centred representation (e.g.
    	    winner is given as name, not by reference to whose fight
    	    fight dict this is).

    '''
    new_fight = copy.deepcopy(fight)

    fighters = new_fight['Fighter']
    _ = new_fight.pop('Fighter')
    sorted_fighters = sorted(fighters)
        
    # set the appropriate winner (from win and loss to actual name of fighter)
    if new_fight['outcome'] == 'win':
        winner = fighters[0]
    elif new_fight['outcome'] == 'loss':
        winner = fighters[1]
    else:
        winner='Draw'


    # if fighters [A,B] come in the order [B,A], we will flip the entries
    # such that we don't end up coding these guys twice. Could probably
    # do this with sets, but think there were some iterablility issues
    flip = sorted_fighters != fighters
    
    if flip:
        for field in new_fight:
            temp = fight[field]
            if type(temp)==list and (field != 'Event'):
                new_fight[field][0]=fight[field][1]
                new_fight[field][1]=fight[field][0]

    new_fight['Result'] = winner
    new_fight['Fighters'] = sorted_fighters
    _= new_fight.pop('outcome')

    return new_fight

"""

def get_fights(fighter,dbfile='fighterdb.sqlite'):
    '''
    Takes a fighters dict, processes the fights and returns a list of
    fights

    Parameters
    ----------
    fighters : dict
    	       A fighters dict, obtained by crawling Fightmetric 
	       (stored in fighters.pickle).

    Returns
    -------
    fights : list
    	     A list of all the fights from fighters   
    '''

    conn = sqlite3.connect(dbfile)
    cur = conn.cursor()

    data = sql_to_list('Fights',cur)

    # So we need to check whether we have repetitions in the Fights and Fighters,
    # and also work out the best way to structure this data.
    
    fights = [fight for fight in data if fighter in [fight['fighter1'],fight['fighter2']]]

    return fights

def build_features(fighters):
    '''
    Builds a feature matrix for classification/regression.
    
    Parameters
    ----------
    fighters : dict
	       Contains all fighter stats; obtained from crawling Fightmetric
    	       (stored in fighters.pickle).
    fights : list (optional)
    	       These are the filtered fights, obtained from calling get_fights(fighters)

    Returns
    -------
    X : pd.DataFrame
	Training data for regressor/classifier. Each column corresponds to a feature
	and each row to an observation (fight)
    y : np.array
    	Fight outcomes. 0 means fighter1 won, 1 means fighter2 won.
    '''
    y = np.zeros(len(fights))

    fights = []
    for fighterName in fighters.keys():
        
        currentFights = get_fights(fighterName)
        
        fights.extend(currentFights)
        

    for i,fight in enumerate(fights):
        
        fighter1=fight['fighter1']
        
        fighter2=fight['fighter2']

        x = build_matchup(fighters,fighter1,fighter2)
        
        if type(x) == type(None):
            import pdb; pdb.set_trace()
        if i == 0:
            Xm = np.zeros([len(fights),len(x.columns)])

        Xm[i,:] = x.as_matrix()

        if fight['winner'] == fighter1:
            y[i] = 0.0
        else:
            y[i] = 1.0

    
    X = pd.DataFrame(Xm,columns=x.columns)
    # Replace nans with means
    for f_dob in ['f1_DOB','f2_DOB']:
        f_no_age=np.array([np.isnan(float(k)) for k in X.loc[:,f_dob]])
        f_age_mean=np.mean(X.loc[~f_no_age,f_dob])        
        X.loc[f_no_age,f_dob] = f_age_mean 

    return X,y

def build_matchup(fighter1,fighter2):
    ''' 
    Builds a single feature vector for a fight between two fighters.
    Note that this only considers fighter stats at the present moment
    in time (except age... maybe)

    Parameters
    ----------
    fighter1 : dict
    	       fighter dictionary containing stats on the first fighter
    fighter2 : dict
    	       fighter dictionary containing stats on the second fighter

    Returns
    -------
    X : pd.DataFrame
    	A single-row data frame corresponding to our feature vector   
    '''

    feature_list = ['height','reach','sapm','slpm','stance','stracc',\
                    'strdef','subavg','tdacc','tdavg','tddef',\
                    'weight','dob','wins','losses','cumtime',\
                    'f1','f2','f3','f4','f5']

    full_feature_list = ['f'+str(i)+'_'+feature for feature in feature_list for i in range(1,3)]
    X = pd.DataFrame(columns=full_feature_list,dtype=float)

    f1_fights = fighters[fighter1]['Fights']
    f2_fights = fighters[fighter2]['Fights']


    # This is to create the binary features for the last K fights
    K_features = ['f1','f2','f3','f4','f5']
    last_K = 5 # last K fights
    n1_fights = 0; n2_fights = 0
    f1_vec = [0]*last_K; f2_vec = [0]*last_K
    for i in range(last_K):
        if i < len(f1_fights):
            f1_fight = f1_fights[i]
            f1_outcome = (f1_fight['winner']==fighter1)*2 - 1
            f1_vec[i] = f1_outcome

        if i < len(f2_fights):
            f2_fight = f2_fights[i]
            f2_outcome = (f2_fight['winner']==fighter2)*2 - 1
            f2_vec[i] = f2_outcome


    exclude_features = ['Wins','Losses','Cum time']
    exclude_features.extend(K_features)
    for feature in feature_list:
        f1='f1_'+feature
        f2='f2_'+feature

        if feature in K_features:
            cf1 = f1_vec[K_features.index(feature)]
            cf2 = f2_vec[K_features.index(feature)]

        if feature not in exclude_features:
            cf1=fighters[fighter1][feature]
            cf2=fighters[fighter2][feature]
            
        if feature == 'dob':
            if cf1=='--':
                cf1=np.nan
            else:
                cf1=float(cf1[-4:])

            if cf2=='--':
                cf2=np.nan
            else:
                cf2=float(cf2[-4:])

        if feature == 'stance':
            if cf1 == 'Orthodox':
                cf1=0.0
            else:
                cf1=1.0
                
            if cf2 == 'Orthodox':
                cf2=0.0
            else:
                cf2=1.0

        if feature == 'Wins':
            cf1 = np.sum([1 for ft in f1_fights if ft['outcome']=='win'])
            cf2 = np.sum([1 for ft in f2_fights if ft['outcome']=='win'])
    
        if feature == 'Losses':
            cf1 = np.sum([1 for ft in f1_fights if ft['outcome']=='loss'])
            cf2 = np.sum([1 for ft in f2_fights if ft['outcome']=='loss'])

        if feature == 'Cum time':
            cf1 = np.sum([ft['Time'] for ft in f1_fights])
            cf2 = np.sum([ft['Time'] for ft in f2_fights])


        X.loc[0,f1]=float(cf1)
        X.loc[0,f2]=float(cf2)

    return X


def sql_to_list(tableName,cur):

    pragmaExpr = 'PRAGMA table_info( %s )'%tableName
    
    cur.execute(pragmaExpr)

    columnData = cur.fetchall()

    columnNames = [t[1] for t in columnData]

    selectExpr = 'SELECT * FROM %s'%tableName
    cur.execute(selectExpr)

    tableData = cur.fetchall()

    dataList = []
    
    for entry in tableData:
        currentFight = {name:entry[i] for i,name in enumerate(columnNames)}
                
        dataList.append(currentFight)

    return dataList

def get_fighters(dbfile='fighterdb.sqlite'):

    conn = sqlite3.connect(dbfile)

    cur = conn.cursor()

    dataList = sql_to_list('Fighters',cur)

    dataDict = {}

    for entry in dataList:
        
        name = entry.pop('name')
        _ = entry.pop('id')

        dataDict[name] = entry

    return dataDict


    

"""
def build_feature(fighter):
'''
    Builds a single feature vector for a given fighter

    Parameters
    ----------
    fighter : dict
    	       fighter dict, contained in fighters.pickle


    Returns
    -------
    X : pd.DataFrame
    	A single-row data frame corresponding to our feature vector   


    feature_list = ['Height','Reach','SApM','SLpM','STANCE','Str. Acc.',\
                    'Str. Def','Sub. Avg.','TD Acc.','TD Avg.','TD Def.',\
                    'Weight','DOB','Wins','Losses','Cum time']

    X = pd.DataFrame(columns=feature_list,dtype=float)

    fights = fighter['Fights']

    for feature in feature_list:
        
        if feature not in ['Wins','Losses','Cum time']:
            cf=fighter[feature]
            
        if feature == 'DOB':
            if cf=='--':
                cf=np.nan
            else:
                cf=float(cf[-4:])


        if feature == 'STANCE':
            if cf == 'Orthodox':
                cf=0.0
            else:
                cf=1.0


        if feature == 'Wins':
            cf = np.sum([1 for ft in fights if ft['outcome']=='win'])
    
        if feature == 'Losses':
            cf = np.sum([1 for ft in fights if ft['outcome']=='loss'])

        if feature == 'Cum time':
            cf = np.sum([ft['Time'] for ft in fights])

        X.loc[0,feature]=float(cf)


    return X
"""
