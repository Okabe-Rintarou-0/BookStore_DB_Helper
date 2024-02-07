from http.cookiejar import FileCookieJar, LWPCookieJar
import os
import re
import inquirer
import pinyin
import requests
from pprint import pprint
from bs4 import BeautifulSoup
import pandas as pd
import mysql.connector
import tqdm
from model import UserInfo, user_infos_from_dict


def get_nick_name(user: UserInfo):
    return user.name

# szm 即首字母
def get_szm(name: str):
    # 留学生
    if name[0].isalpha() and name[0].isascii():
        sub_names = [sub_name[0] for sub_name in name.split(' ')]
        name = ''.join(sub_names)
    else:
        name = pinyin.get_initial(name, delimiter="")

    return name


def get_user_name(user: UserInfo):
    name = get_szm(user.name)
    # 取末尾四位
    id = user.sortable_name.split("-")[0][-4:]
    return name + id


def get_password(user: UserInfo):
    return get_szm(user.name)


def save_all_users(users, save_path, format='excel'):
    df = pd.DataFrame(users, columns=['用户名', '昵称', '密码'])
    if format == 'excel':
        df.to_excel(save_path, index=False)
    elif format == 'csv':
        df.to_csv(save_path, index=False)


if __name__ == '__main__':
    session = requests.session()
    login_url = 'https://oc.sjtu.edu.cn/login/openid_connect'
    courses_url = 'https://oc.sjtu.edu.cn/courses'
    while True:
        if os.path.exists('JAAuthCookie.txt'):
            print('检测到已保存的 JAAuthCookie，加载...', end='')
            with open('JAAuthCookie.txt', 'r') as f:
                JAAuthCookie = f.read()
            print('Done.')
        else:
            JAAuthCookie = input(
                "请从 https://jaccount.sjtu.edu.cn/jaccount/ 的 Cookies 中正确复制 'JAAuthCookie' 字段：\n")
        login_cookies = {
            'JAAuthCookie': JAAuthCookie,
        }
        print('现在开始登录...')
        res = session.get(login_url, cookies=login_cookies)
        if res.status_code == 200 and not "https://jaccount.sjtu.edu.cn/jaccount/jalogin" in res.request.url:
            print('登录成功！保存最新的 JAAuthCookie...', end='')
            with open('JAAuthCookie.txt', 'w') as f:
                f.write(JAAuthCookie)
            print('Done')
            break
        elif os.path.exists('JAAuthCookie.txt'):
            print('登录失败！删除旧的 JAAuthCookie...', end='')
            os.remove('JAAuthCookie.txt')
            print('Done')
        else:
            print("登录失败！")

    print('开始搜索可用的课程...', end='')
    content = session.get(courses_url).content
    soup = BeautifulSoup(content, 'html.parser')
    courses = soup.find_all(
        'a', {'title': True, 'href': re.compile(r"/courses/\d+")})
    courses = [(course.get('title'), re.findall(r"/courses/(\d+)", course.get('href'))[0])
               for course in courses]
    enrolled_as = [item.get_text().strip() for item in soup.find_all(
        'td', {'class': 'course-list-enrolled-as-column'})]
    courses = [(t[0], t[1], s) for t, s in zip(courses, enrolled_as)]
    print('Done')

    if len(courses) == 0:
        print('没有可用的课程！')
        exit(0)

    courses = list(filter(lambda x: x[2] == '助教', courses))

    courses_selection = [
        course[0]
        for course in courses
    ]
    questions = [
        inquirer.List('course',
                      message="请选择课程",
                      choices=courses_selection
                      )]

    selected_course_name = inquirer.prompt(questions)['course']
    print(f'你选择了课程 "{selected_course_name}"')
    selected_course = list(
        filter(lambda x: x[0] == selected_course_name, courses))[0]

    course_id = selected_course[1]
    per_page = 50
    print('正在读取名单...')
    page_index = 1
    all_users = []

    while True:
        try:
            print(f"读取第{page_index}页数据.")
            url = f'https://oc.sjtu.edu.cn/api/v1/courses/{course_id}/users?per_page={per_page}&page={page_index}'

            res = session.get(url)
            data = res.json()
            users = user_infos_from_dict(data)
            if len(users) == 0:
                break
            all_users.extend(users)
            page_index += 1
        except Exception as e:
            print(e)
            break

    all_users = [(get_user_name(user), get_nick_name(user), get_password(user))
                 for user in all_users]

    questions = [inquirer.Confirm('need_save', message="是否需要保存名单")]
    need_save = inquirer.prompt(questions)['need_save']

    if need_save:
        questions = [
            inquirer.List('format', message="请输入保存格式：",
                          choices=['csv', 'excel']),
            inquirer.Text('save_path', message="请输入保存路径")]
        answers = inquirer.prompt(questions)
        format = answers['format']
        save_path = answers['save_path']
        save_all_users(all_users, save_path, format)
        print('保存成功！')

    print('准备导入数据库...')
    DEFAULT_HOST_SELECTION = '本地（localhost)'
    CUSTOM_HOST_SELECTION = '远程 host'
    questions = [
        inquirer.List('host', message="请选择 Mysql 数据库 Host",
                      choices=[DEFAULT_HOST_SELECTION, CUSTOM_HOST_SELECTION]),
    ]
    host = inquirer.prompt(questions)['host']
    if host == DEFAULT_HOST_SELECTION:
        host = 'localhost'
    else:
        questions = [inquirer.Text('host', message='请输入远程 host')]
        host = inquirer.prompt(questions)['host']

    questions = [inquirer.Text('password', message='请输入密码')]
    password = inquirer.prompt(questions)['password']
    conn = mysql.connector.connect(
        host=host,
        user='root',
        password=password,
        database="bookstore"
    )

    cursor = conn.cursor()
    cursor.execute("SELECT username FROM user_auth")
    result = cursor.fetchall()

    old_username_set = set([row[0] for row in result])
    
    for user in tqdm.tqdm(all_users, desc='导入数据库'):
        username = user[0]
        nickname = user[1]
        password=user[2]
        if username in old_username_set:
            continue

        cursor.execute(f"INSERT into user(nickname, balance) value ('{nickname}',100000000)")
        user_id = cursor.lastrowid
        cursor.execute(f"INSERT into user_auth(identity, password, username, user_id) value (0,'{password}','{username}',{user_id})")

    conn.commit()
    print('完成🎉 程序退出。')
    cursor.close()
    conn.close()
    