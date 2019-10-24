import urllib
import re
import discord
from util import NoResultsError, get_blurb, get_soup
from datetime import datetime
from difflib import SequenceMatcher

bbref_url = 'https://www.basketball-reference.com'
search_url = bbref_url + '/search/search.fcgi?search={search}'
last_url = bbref_url + '/play-index/span_stats.cgi?html=1&page_id={page_id}&table_id=pgl_basic&range={last}-{career}'
espn_search_url = 'http://www.espn.com/nba/players/_/search/{search}'
top_url = bbref_url + '/friv/dailyleaders.fcgi'
letters = re.compile('[^a-zA-Z]')
DEBUG = False


def get_basketball_blurb(first, last):
    return get_blurb(first, last, 'nba')


def get_log(search):
    log_map = get_log_map(search)
    embed = format_log(log_map)
    return embed


def get_last(search, last):
    avg_log_map = get_avg_map(search, last)
    title = "Average stats for **{player}** over his last " + f"{last} games"
    embed = format_log(avg_log_map, title=title, add_date_header=False)
    return embed


def get_live_log(search):
    live_log_map = get_live_log_map(search)
    title = "Live(ish) stats for **{player}**"
    embed = format_live_log(live_log_map, title=title)
    return embed


def get_highlight():
    highlight_map = get_highlight_lowlight_map(highlight=True)
    embed = None
    if highlight_map:
        title = "Stat line of the day for **{date}**: **{player}** vs **{opp}**"
        embed = format_log(highlight_map, title=title, name_only=False, add_date_header=False)
    return embed


def get_lowlight():
    lowlight_map = get_highlight_lowlight_map(highlight=False)
    embed = None
    if lowlight_map:
        title = "Lowlight of the day for **{date}**: **{player}** vs **{opp}**"
        embed = format_log(lowlight_map, title=title, name_only=False, add_date_header=False)
    return embed


def get_log_map(search):
    name, table = get_player_log_table(search=search)
    row = table.find_all(lambda tag: tag.name == 'tr' and 'pgl_basic' in tag.get('id', '')).pop()
    stat_map = index_row(row)
    stat_map['name'] = name
    return stat_map


def get_avg_map(search, last):
    name, table = get_avg_log_table(search=search, last=last)
    row = table.findChild('tr')
    stat_map = index_row(row)
    stat_map['name'] = name
    return stat_map


def get_live_log_map(search, url=None):
    full_search = ' '.join(search)
    if url:
        soup = get_soup(url)
    else:
        last_name = format_live_search(search)
        soup = get_soup(espn_search_url.format(search=last_name))
    name_tag = soup.find('meta', attrs={'property': 'og:title'})
    if name_tag:
        try:
            name = name_tag.get('content').replace(' Stats, News, Bio | ESPN', '')
            is_playing = soup.find('h3', class_='Card__Header__Title Card__Header__Title--no-theme', text='Current Game')
            if is_playing:
                log_map = {}
                game_summary = soup.findChild('a', attrs={'title': 'Game Summary'})
                stats_table = game_summary.find_next('tbody', class_='Table__TBODY')
                stats = [row.text for row in stats_table.findChildren(lambda tag: tag.name == 'td')]
                log_map['mp'] = stats[2]
                log_map['fg_pct'] = stats[3]
                log_map['tp_pct'] = stats[4]
                log_map['ft_pct'] = stats[5]
                log_map['trb'] = int(float(stats[6]))
                log_map['ast'] = int(float(stats[7]))
                log_map['blk'] = int(float(stats[8]))
                log_map['stl'] = int(float(stats[9]))
                log_map['pf'] = int(float(stats[10]))
                log_map['tov'] = int(float(stats[11]))
                log_map['pts'] = int(float(stats[12]))
                log_map['name'] = name
                return log_map
            else:
                raise NoResultsError(f"{name} isn't currently playing")
        except Exception as ex:
            raise ex
    else:
        results_table = soup.find('div', attrs={'id': 'my-players-table'}).find_next('table')
        col_header = results_table.findChild('tr', class_='colhead')
        if col_header:
            player_results = results_table.findChildren(lambda tag: tag.name == 'tr' and tag.get('class') not in ['stathead', 'colhead'])
            result_map = {}
            for result in player_results:
                a = result.find_next('a')
                name = a.text.split(', ')
                name = f'{name[1]} {name[0]}'
                match = SequenceMatcher(None, full_search, name).ratio()
                result_map[a.get('href')] = match
            player_href = sorted(result_map, key=result_map.get, reverse=True)[0]
            return get_live_log_map(search, player_href)
        else:
            raise NoResultsError(f"No results for '{full_search}'")


def format_live_search(search):
    if len(search) == 2 or len(search) == 3:
        return search[1]
    elif len(search) == 1:
        return search[0]
    else:
        raise ValueError('Malformed search string or something?')


def index_row(row):
    stat_map = {}
    for cell in row.findChildren('td'):
        stat = cell.get('data-stat', default=None)
        if stat:
            if stat == 'player':
                stat_map['name'] = cell.text
            else:
                stat_map[stat] = cell.text
    if 'date_game' not in stat_map:
        stat_map['date_game'] = datetime.today().strftime('%Y-%m-%d')
    if DEBUG:
        print(stat_map)
    return stat_map


def get_highlight_lowlight_map(highlight=True):
    top_soup = get_soup(top_url)
    table = top_soup.find('table', attrs={'id': 'stats'})
    if not table:
        return None
    else:
        rows = table.find('tbody').findChildren(lambda tag: tag.name == 'tr' and not 'thead' == tag.get('class')
                                                and tag.findChild(lambda child: child.name == 'td'
                                                                  and child.get('data-stat') == 'mp'
                                                                  and int(child.text.split(':')[0]) >= 25))
    if highlight:
        return index_row(rows[0])
    else:
        return index_row(rows[-1])


def get_player_log_table(search):
    player_soup = get_player_page(search)
    log_holder = player_soup.find('span', text="Game Logs")
    name_node = player_soup.find('h1', attrs={'itemprop': 'name'})
    name = name_node.text
    game_log_link_list = log_holder.find_next('div').find('ul').findChildren('a')
    game_log_link = game_log_link_list.pop()
    if 'Playoffs' in game_log_link.text:
        game_log_link = game_log_link_list.pop()
    href = game_log_link.get('href')
    log_soup = get_soup(bbref_url + href)
    table = log_soup.find('table', attrs={'id': 'pgl_basic'}).find('tbody')
    return name, table


def get_avg_log_table(search, last):
    player_soup = get_player_page(search)
    career_games = int(player_soup.find('h4', class_='poptip', attrs={'data-tip': 'Games'}).find_next('p').find_next('p').text)
    name_node = player_soup.find('h1', attrs={'itemprop': 'name'})
    name = name_node.text
    if last > career_games:
        raise ValueError(f'{name} has only played {career_games} career games')
    page_id = player_soup.find('link', attrs={'rel': 'canonical'}).get('href').split('/')[-1].split('.')[0]
    log_soup = get_soup(last_url.format(page_id=page_id, last=career_games - last + 1, career=career_games))
    table = log_soup.find('table', attrs={'id': 'pgl_basic_span'}).find('tbody')
    return name, table


def get_player_page(search=None, url=None):
    soup = get_soup(url if url else search_url.format(search=urllib.parse.quote(search)))
    log_holder = soup.find('span', text="Game Logs")
    if log_holder:
        return soup
    elif soup.findChild('div', class_='search-results'):
        nba_players = soup.find('div', attrs={"id": "players"})
        if nba_players:
            results = nba_players.findChildren('div', class_='search-item')
            if len(results) == 1:
                href = nba_players.find_next('div', class_='search-item-url').text
                return get_player_page(url=bbref_url + href)
            else:
                result_map = {}
                for result in results:
                    a = result.find_next('div', class_='search-item-name').find_next('a')
                    name = letters.sub('', a.text)
                    match = SequenceMatcher(None, search, name).ratio()
                    result_map[a.get('href')] = match
                href = sorted(result_map, key=result_map.get, reverse=True)[0]
                return get_player_page(url=bbref_url + href)
        else:
            raise NoResultsError("No NBA results for %s" % search)
    else:
        raise NoResultsError("No results for %s" % search)


def format_live_log(log_map, title="**{player}**'s most recent game"):
    mins = log_map['mp']
    pts = log_map['pts']
    fgp = log_map['fg_pct']
    tpp = log_map['tp_pct']
    ftp = log_map['ft_pct']
    reb = log_map['trb']
    ast = log_map['ast']
    stl = log_map['stl']
    blk = log_map['blk']
    pf = log_map['pf']
    to = log_map['tov']
    name = log_map['name']
    title = title.format(player=name)
    log_string = f"**MIN**: {mins}\n**PTS**: {pts} ({fgp} **FG%**, {tpp} **3P%**, {ftp} **FT%**)" \
                 f"\n**REB**: {reb}\n**AST**: {ast}\n**STL**: {stl}\n**BLK**: {blk}\n**TO**: {to}\n**PF**: {pf}"
    if DEBUG:
        print(title)
        print(log_string)
    return discord.Embed(title=title, description=log_string)


def format_log(log_map, title="**{player}**'s most recent game", name_only=True, add_date_header=True):
    date = log_map.get('date_game', None)
    opp = log_map.get('opp_id', None)
    mins = log_map['mp']
    pts = log_map['pts']
    fgm = log_map['fg']
    fga = log_map['fga']
    fgp = log_map['fg_pct']
    tpm = log_map['fg3']
    tpa = log_map['fg3a']
    ftm = log_map['ft']
    fta = log_map['fta']
    reb = log_map['trb']
    ast = log_map['ast']
    stl = log_map['stl']
    blk = log_map['blk']
    pf = log_map['pf']
    to = log_map['tov']
    name = log_map['name']
    if name_only:
        title = title.format(player=name)
    else:
        title = title.format(player=name, date=date, opp=opp)
    date_header = f"**{date}** vs **{opp}**\n"
    log_string = (date_header if add_date_header else "") + \
                 f"**MIN**: {mins}\n**PTS**: {pts} ({fgm}/{fga}, {fgp} **FG%**, {tpm}/{tpa} **3P**, {ftm}/{fta} **FT**)" \
                 f"\n**REB**: {reb}\n**AST**: {ast}\n**STL**: {stl}\n**BLK**: {blk}\n**TO**: {to}\n**PF**: {pf}"
    if DEBUG:
        print(title)
        print(log_string)
    return discord.Embed(title=title, description=log_string)
