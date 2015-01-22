import pymysql
from pymysql.err import DataError

conn = pymysql.connect(host='test', port=3306, user='test', passwd='test', db='bug_report', charset='utf8')

#pullreq table: author, project, pullreqID, merge commit of the pullreq
def create_pullreq():
    sql = "create table github.pullrequest (Author varchar(50),Project varchar(50),Pullreq int,Commit varchar(50))"
    cur = conn.cursor()
    cur.execute(sql)
    conn.commit()
    cur.close()

def insert_pullreq(author, project, pullreq, commit):
    sql = "insert into github.pullrequest values(\""+author+"\",\""+project+"\",\""+pullreq+"\",\""+commit+"\")"
    cur = conn.cursor()
    cur.execute(sql)
    conn.commit()
    cur.close()

def get_pullreq(author,project):
    pullreq = []
    sql = "select Pullreq from github.pullrequest where Author=\"" + author + '\" and Project=\"' + project + '\"'
    cur = conn.cursor()
    cur.execute(sql)
    for row in cur.fetchall():
        pullreq.append(str(row[0]))
    cur.close()
    return pullreq

#forkrepo table: author, project, upstream repo, pullreq sent to upstream, list of commits in the pullreq
def create_forkrepo():
    sql = "create table github.forkrepo (Author varchar(50),Project varchar(50),Upstream varchar(100),Pullreq int,Commits varchar(5000))"
    cur = conn.cursor()
    cur.execute(sql)
    conn.commit()
    cur.close()

def insert_forkrepo(author,project,upstream,pullreq,commits):
    sql = "insert into github.forkrepo values(\"" + author + "\",\"" + project + "\",\"" + upstream + "\",\"" + pullreq + '\",\"' + str(commits) + "\")"
    cur = conn.cursor()
    cur.execute(sql)
    conn.commit()
    cur.close()

#get all forks of the upstream
def get_forkrepo(upstream):
    list = []
    sql = "select Author,Project from github.forkrepo where Upstream=\""+upstream+"\""
    cur = conn.cursor()
    cur.execute(sql)
    for row in cur.fetchall():
        #distinct forks (note in the db it's arrange on pullrequest, so forks might duplicate)
        if (row[0],row[1]) not in list:
            list.append((row[0],row[1]))
    cur.close()
    return list

#Commit, Author, Project, IsFork, Branch, Evol list
def create_commit():
    sql = "create table github.commit (Commit varchar(50),Author varchar(50),Project varchar(50),IsFork int,Branches varchar(5000),Evolution varchar(5000))"
    cur = conn.cursor()
    cur.execute(sql)
    conn.commit()
    cur.close()

def insert_commits(commit,author,project,isfork,branches):
    sql = "insert into github.commit values(\""+commit+'\",\"'+author+'\",\"'+project+'\",\"'+str(isfork)+'\",\"'+str(branches)+'\",\"\")'
    cur = conn.cursor()
    cur.execute(sql)
    conn.commit()
    cur.close()

#get the list of commits
def get_commits(author,project,isfork):
    commits = []
    if isfork:
        sql = 'select Commits from github.forkrepo where Author=\"'+author+"\" and Project=\""+project+"\""
    else:
        sql = 'select Commit from github.pullrequest where Author=\"'+author+"\" and Project=\""+project+"\""
    cur = conn.cursor()
    cur.execute(sql)
    for row in cur.fetchall():
        raw = row[0]
        if isfork:
            raw = raw[1:len(raw)-1]
            #here should be ', ' instead of ','
            list = raw.split(', ')
            for l in list:
                commits.append(l[1:len(l)-1])
        else:
            commits.append(raw)
    cur.close()
    return commits

def get_branches(commit, author, project):
    branches = []
    sql = 'select Branches from github.commit where Commit=\"'+commit+'\" and Author=\"'+author+'\" and Project=\"'+project + '\"'
    cur = conn.cursor()
    cur.execute(sql)
    for row in cur.fetchall():
        raw = row[0]
        raw = raw[1:len(raw)-1]
        list = raw.split(', ')
        for l in list:
            branches.append(l[1:len(l)-1])
    cur.close()
    return branches

#list of (commit, author, repo)
def get_commit_repo():
    results = []
    sql = 'select Commit,Author,Project from github.commit'
    cur = conn.cursor()
    cur.execute(sql)
    for row in cur.fetchall():
        results.append((row[0],row[1],row[2]))
    cur.close()
    return results

def update_evolution(commit,author,evol):
    sql = 'update github.commit set Evolution=\"'+str(evol)+'\" where Commit=\"'+commit+'\" and Author=\"'+author+'\"'
    cur = conn.cursor()
    try:
        cur.execute(sql)
        conn.commit()
    except DataError as e:
        print(e)
        pass
    cur.close()

#distinct fork authors from commit table
def get_fork_author():
    results = []
    sql = 'select distinct Author from github.commit where IsFork=1'
    cur = conn.cursor()
    cur.execute(sql)
    for row in cur.fetchall():
        results.append(row[0])
    cur.close()
    return results

#for each fork repo, get all its evolution commits identified from pullreq commit
def get_fork_evol_commits(author):
    results = []
    sql = 'select Evolution from github.commit where Author=\''+author+'\''
    cur = conn.cursor()
    cur.execute(sql)
    for row in cur.fetchall():
        raw = row[0]
        if len(raw) == 0 or raw == '[]':
            continue
        raw = raw[1:len(raw)-1]
        list = raw.split('), ')
        for l in list:
            commit = l[2:l.find(',')-1]
            if commit not in results:
                results.append(commit)
    cur.close()
    return results

#for each fork repo, get all its commits that are ever contained in pull requests
def get_fork_pullreq_commits(author):
    results = []
    sql = 'select Commits from github.forkrepo where Author=\''+author+'\''
    cur = conn.cursor()
    cur.execute(sql)
    for row in cur.fetchall():
        raw = row[0]
        raw = raw[1:len(raw)-1]
        list = raw.split(', ')
        for l in list:
            commit = l[1:len(l)-1]
            if commit not in results:
                results.append(commit)
    cur.close()
    return results