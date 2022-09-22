import configparser
import datetime

import discord
from discord.ext import commands
from discord.ui import Button, View, Select
import src.assets as assets
import src.db_controller as db
import src.Ump.robo_ump as robo_ump
import src.sheets_reader as sheets

config_ini = configparser.ConfigParser()
config_ini.read('config.ini')


class Game(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.ump_hq = self.bot.get_channel(int(config_ini['Channels']['ump_hq']))

    @commands.command(brief='',
                      description='')
    @commands.dm_only()
    async def dm_swing(self, ctx, swing: int):
        if not 0 < swing <= 1000:
            await ctx.send('Not a valid pitch dum dum.')
            return
        game = await robo_ump.fetch_game_swing(ctx, self.bot)
        data = (ctx.message.id, ctx.message.created_at) + game
        league, season, session, game_id = game
        db.update_database('''UPDATE pitchData SET swing_src=%s, swing_submitted=%s WHERE league=%s AND season=%s AND session=%s AND game_id=%s''', data)
        state, = db.fetch_one('SELECT state FROM gameData WHERE league=%s AND season=%s AND session=%s AND gameID=%s', (league, season, session, game_id))
        pitch_src, = db.fetch_one('SELECT pitch_src FROM pitchData WHERE league=%s AND season=%s AND session=%s AND game_id=%s', (league, season, session, game_id))
        await ctx.message.add_reaction('👍')
        if pitch_src and state != 'PAUSED':
            robo_ump.set_state(league, season, session, game_id, 'WAITING FOR RESULT')
        robo_ump.log_msg(f'{ctx.author.mention} swung via DM for {game[0]} {game[1]}.{game[2]}.{game[3]} ')

    @commands.command(brief='',
                      description='')
    @commands.dm_only()
    async def gm_steal(self, ctx, team: str, swing: int, *, steal_type: str):
        if not 0 < swing <= 1000:
            await ctx.send('Not a valid pitch dum dum.')
            return
        if not steal_type.upper() in assets.steal_types:
            await ctx.send(f'Not a valid steal type. Valid types are \n```{assets.steal_types}```')
            return
        season, session = robo_ump.get_current_session(team)
        league, season, session, game_id = robo_ump.fetch_game_team(team, season, session)
        sheet_id = robo_ump.get_sheet(league, season, session, game_id)
        data = (ctx.message.id, ctx.message.created_at, league, season, session, game_id)
        event = robo_ump.set_event(sheet_id, steal_type.upper())
        db.update_database('''UPDATE pitchData SET swing_src=%s, swing_submitted=%s WHERE league=%s AND season=%s AND session=%s AND game_id=%s''', data)
        await ctx.message.add_reaction('👍')
        await ctx.send(f'Event set to {event}')
        robo_ump.log_msg(f'{ctx.author.mention} issued a GM steal via DMs for {league} {season}.{session}.{game_id}')
        data = ('WAITING FOR RESULT', league, season, session, game_id)
        db.update_database('''UPDATE gameData SET state=%s WHERE league=%s AND season=%s AND session=%s AND gameID=%s''', data)
        robo_ump.log_msg(f'Game {league} {season}.{session}.{game_id} awaiting result...')

    @commands.command(brief='',
                      description='')
    async def ibb(self, ctx, team: str):
        season, session = robo_ump.get_current_session(team)
        league, season, session, game_id = robo_ump.fetch_game_team(team, season, session)
        sheet_id = robo_ump.get_sheet(league, season, session, game_id)
        event = robo_ump.set_event(sheet_id, 'IBB')
        data = ('WAITING FOR RESULT', league, season, session, game_id)
        db.update_database('''UPDATE gameData SET state=%s WHERE league=%s AND season=%s AND session=%s AND gameID=%s''', data)
        await ctx.send(f'Event set to {event}')
        robo_ump.log_msg(f'{ctx.author.mention} issued an IBB for {league} {season}.{session}.{game_id}')

    @commands.command(brief='',
                      description='')
    async def infield_in(self, ctx, team: str):
        season, session = robo_ump.get_current_session(team)
        league, season, session, game_id = robo_ump.fetch_game_team(team, season, session)
        sheet_id = robo_ump.get_sheet(league, season, session, game_id)
        event = robo_ump.set_event(sheet_id, 'Infield In')
        await ctx.send(f'Event set to {event}')
        robo_ump.log_msg(f'{ctx.author.mention} set Infield In for {league} {season}.{session}.{game_id}')

    @commands.command(brief='',
                      description='')
    async def conditional_swing(self, ctx, team: str, batter: discord.Member, *, notes: str):
        await ctx.message.add_reaction('👍')
        season, session = robo_ump.get_current_session(team)
        game = robo_ump.fetch_game_team(team, season, session)
        conditional_batter = robo_ump.get_player_from_discord(batter.id)
        conditional_swing_requested = ctx.message.created_at
        data = (conditional_batter, conditional_swing_requested, notes) + game
        sql = '''UPDATE pitchData SET conditional_batter=%s, conditional_swing_requested=%s, conditional_swing_notes=%s WHERE league=%s AND season=%s AND session=%s AND game_id=%s'''
        db.update_database(sql, data)
        await batter.send(f'{ctx.author.mention} has requested a conditional swing for {team.upper()}. Please reply with a swing number to be used at the following condition: {notes}')

        def wait_for_response(msg):
            return msg.content.isnumeric() and 0 < int(msg.content) <= 1000

        await ctx.send('Conditional swing request sent to batter.')
        conditional_swing = await self.bot.wait_for('message', check=wait_for_response)
        sql = '''UPDATE pitchData SET conditional_swing_src=%s WHERE league=%s AND season=%s AND session=%s AND game_id=%s'''
        db.update_database(sql, (conditional_swing.id,) + game)
        await conditional_swing.add_reaction('👍')
        await ctx.send('Conditional swing submitted.')

    @commands.command(brief='',
                      description='')
    async def submit_conditional_swing(self, ctx, swing: int):
        if not 0 < swing <= 1000:
            await ctx.send('Not a valid pitch dum dum.')
            return
        game = await robo_ump.fetch_game_conditional_swing(ctx, self.bot)
        data = (ctx.message.id, ctx.message.created_at) + game
        db.update_database('''UPDATE pitchData SET conditional_swing_src=%s WHERE league=%s AND season=%s AND session=%s AND game_id=%s''', data)
        await ctx.message.add_reaction('👍')

    @commands.command(brief='',
                      description='')
    async def submit_conditional_pitch(self, ctx, swing: int):
        if not 0 < swing <= 1000:
            await ctx.send('Not a valid pitch dum dum.')
            return
        game = await robo_ump.fetch_game_conditional_pitch(ctx, self.bot)
        data = (ctx.message.id,) + game
        db.update_database('''UPDATE pitchData SET conditional_pitch_src=%s WHERE league=%s AND season=%s AND session=%s AND game_id=%s''', data)
        await ctx.message.add_reaction('👍')

    @commands.command(brief='',
                      description='')
    async def conditional_pitch(self, ctx, team: str, batter: discord.Member, *, notes: str):
        season, session = robo_ump.get_current_session(team)
        game = robo_ump.fetch_game_team(team, season, session)
        league, season, session, game_id = game
        conditional_pitcher = robo_ump.get_player_from_discord(batter.id)
        conditional_pitch_requested = ctx.message.created_at
        data = (conditional_pitcher, conditional_pitch_requested, notes, league, season, session, game_id)
        sql = '''UPDATE pitchData SET conditional_pitcher=%s, conditional_pitch_requested=%s, conditional_pitch_notes=%s WHERE league=%s AND season=%s AND session=%s AND game_id=%s'''
        db.update_database(sql, data)
        await batter.send(
            f'{ctx.author.mention} has requested a conditional pitch for {team.upper()}. Please reply with a pitch number to be used at the following condition: {notes}')

        def wait_for_response(msg):
            return msg.content.isnumeric() and 0 < int(msg.content) <= 1000

        await ctx.send('Conditional pitch request sent to pitcher.')
        conditional_pitch = await self.bot.wait_for('message', check=wait_for_response)
        sql = '''UPDATE pitchData SET conditional_pitch_src=%s WHERE league=%s AND season=%s AND session=%s AND game_id=%s'''
        db.update_database(sql, (conditional_pitch.id,) + game)
        await conditional_pitch.add_reaction('👍')
        await ctx.send('Conditional pitch submitted.')

    @commands.command(brief='',
                      description='')
    async def request_sub(self, ctx, team: str):
        season, session = robo_ump.get_current_session(team)
        league, season, session, game_id = robo_ump.fetch_game_team(team, season, session)
        game = robo_ump.fetch_game_team(team, season, session)
        logo_url, color = db.fetch_one('SELECT logo_url, color FROM teamData WHERE abb=%s', (team,))
        thread_url, sheet_id, home_team, away_team, state = db.fetch_one('SELECT threadURL, sheetID, homeTeam, awayTeam, state FROM gameData WHERE league=%s AND season=%s AND session=%s AND gameID=%s', game)
        if team.upper() == home_team:
            sub_list = sheets.read_sheet(sheet_id, assets.calc_cell2['home_sub_list'])
        elif team.upper() == away_team:
            sub_list = sheets.read_sheet(sheet_id, assets.calc_cell2['away_sub_list'])
        else:
            await ctx.message.add_reaction('⁉')
            return
        sub_list_dropdown = []
        positions_select = []
        for sub in sub_list:
            sub_list_dropdown.append(discord.SelectOption(label=sub[0]))
        for pos in assets.valid_positions:
            positions_select.append(discord.SelectOption(label=pos))
        player_out_select = Select(placeholder='Player Out', options=sub_list_dropdown)
        player_in_select = Select(placeholder='Player In', options=sub_list_dropdown)
        positions_select = Select(placeholder='Position', options=positions_select)
        confirm = Button(label="Submit Request", style=discord.ButtonStyle.green)
        cancel = Button(label="Cancel", style=discord.ButtonStyle.red)

        async def player_out_callback(interaction):
            embed.add_field(name='Player Out', value=player_out_select.values[0])
            await interaction.response.edit_message(embed=embed)

        async def player_in_callback(interaction):
            embed.add_field(name='Player In', value=player_in_select.values[0])
            await interaction.response.edit_message(embed=embed)

        async def position_callback(interaction):
            embed.add_field(name='Position', value=positions_select.values[0])
            await interaction.response.edit_message(embed=embed)

        async def send_request(interaction):
            await self.ump_hq.send(embed=embed, view=robo_ump.umpdate_buttons(sheet_id, embed, league, season, session, game_id))
            robo_ump.set_state(league, season, session, game_id, 'WAITING FOR UMP CONFIRMATION')
            await interaction.response.edit_message(content='Request sent.', view=None, embed=embed)

        async def cancel_request(interaction):
            await interaction.response.edit_message(content='Request cancelled.', view=None, embed=None)
            return

        player_out_select.callback = player_out_callback
        player_in_select.callback = player_in_callback
        positions_select.callback = position_callback
        confirm.callback = send_request
        cancel.callback = cancel_request

        view = View(timeout=None)
        view.add_item(player_out_select)
        view.add_item(player_in_select)
        view.add_item(positions_select)
        view.add_item(confirm)
        view.add_item(cancel)

        embed = discord.Embed(title='Substitution Request', description=f'{ctx.author.mention} has requested the following substitution.\n\nPlease update the **Subs** tab on the Ump Helper sheet.', color=discord.Color(value=int(color, 16)))
        embed.set_author(name=f'{ctx.author}', icon_url=logo_url)
        embed.add_field(name='State', value=state, inline=False)
        await ctx.send(content='Use the drop down menus to select the player you want subbed out, the player you want subbed in, and their new position. You can submit multiple substitutions in one request. If you mess up, hit cancel and start over. When you hit submit, a request will be sent to #umpires in main for the sub to be processed.', view=view, embed=embed)

    @commands.command(brief='',
                      description='')
    async def request_position_change(self, ctx, team: str):
        season, session = robo_ump.get_current_session(team)
        league, season, session, game_id = robo_ump.fetch_game_team(team, season, session)
        game = robo_ump.fetch_game_team(team, season, session)
        logo_url, color = db.fetch_one('SELECT logo_url, color FROM teamData WHERE abb=%s', (team,))
        thread_url, sheet_id, home_team, away_team, state = db.fetch_one('SELECT threadURL, sheetID, homeTeam, awayTeam, state FROM gameData WHERE league=%s AND season=%s AND session=%s AND gameID=%s',game)
        if team.upper() == home_team:
            sub_list = sheets.read_sheet(sheet_id, assets.calc_cell2['home_sub_list'])
        elif team.upper() == away_team:
            sub_list = sheets.read_sheet(sheet_id, assets.calc_cell2['away_sub_list'])
        else:
            await ctx.message.add_reaction('⁉')
            return
        sub_list_dropdown = []
        positions_select = []
        for sub in sub_list:
            sub_list_dropdown.append(discord.SelectOption(label=sub[0]))
        for pos in assets.valid_positions:
            positions_select.append(discord.SelectOption(label=pos))
        player_select = Select(placeholder='Player', options=sub_list_dropdown)
        old_pos_select = Select(placeholder='Old Position', options=positions_select)
        new_pos_select = Select(placeholder='New Position', options=positions_select)
        confirm = Button(label="Submit Request", style=discord.ButtonStyle.green)
        cancel = Button(label="Cancel", style=discord.ButtonStyle.red)

        async def player_callback(interaction):
            embed.add_field(name='Player', value=player_select.values[0])
            await interaction.response.edit_message(embed=embed)

        async def old_position_callback(interaction):
            embed.add_field(name='Old Position', value=old_pos_select.values[0])
            await interaction.response.edit_message(embed=embed)

        async def new_position_callback(interaction):
            embed.add_field(name='New Position', value=new_pos_select.values[0])
            await interaction.response.edit_message(embed=embed)

        async def send_request(interaction):
            await self.ump_hq.send(embed=embed, view=robo_ump.umpdate_buttons(sheet_id, embed, league, season, session, game_id))
            robo_ump.set_state(league, season, session, game_id, 'WAITING FOR UMP CONFIRMATION')
            await interaction.response.edit_message(content='Request sent.', view=None, embed=embed)

        async def cancel_request(interaction):
            await interaction.response.edit_message(content='Request cancelled.', view=None, embed=None)
            return

        player_select.callback = player_callback
        old_pos_select.callback = old_position_callback
        new_pos_select.callback = new_position_callback
        confirm.callback = send_request
        cancel.callback = cancel_request

        view = View(timeout=None)
        view.add_item(player_select)
        view.add_item(old_pos_select)
        view.add_item(new_pos_select)
        view.add_item(confirm)
        view.add_item(cancel)

        embed = discord.Embed(title='Position Change Request', description=f'{ctx.author.mention} has requested the following position change.\n\nPlease update the **Subs** tab on the Ump Helper sheet.', color=discord.Color(value=int(color, 16)))
        embed.set_author(name=f'{ctx.author}', icon_url=logo_url)
        embed.add_field(name='State', value=state, inline=False)
        await ctx.send(content='Use the drop down menus to select the relevant player, their current position, and their new position. You can submit multiple position changes in one request. If you mess up, hit cancel and start over. When you hit submit, a request will be sent to #umpires in main for the sub to be processed.', view=view, embed=embed)
        return None

    @commands.command(brief='',
                      description='')
    async def request_auto_k(self, ctx, team: str):
        season, session = robo_ump.get_current_session(team)
        league, season, session, game_id = robo_ump.fetch_game_team(team, season, session)
        game = robo_ump.fetch_game_team(team, season, session)
        thread_url, sheet_id = db.fetch_one('SELECT threadURL, sheetID FROM gameData WHERE league=%s AND season=%s AND session=%s AND gameID=%s', game)
        sql = '''SELECT swing_requested, swing_submitted, conditional_batter, conditional_swing_requested, conditional_swing_src, conditional_swing_notes FROM pitchData WHERE league=%s AND season=%s AND session=%s AND game_id=%s'''
        swing_requested, swing_submitted, conditional_batter, conditional_swing_requested, conditional_swing_src, conditional_swing_notes = db.fetch_one(sql, game)
        logo_url, color = db.fetch_one('SELECT logo_url, color FROM teamData WHERE abb=%s', (team,))

        embed = discord.Embed(title='Auto K Request', description=f'{ctx.author.mention} has requested an auto K. Please investigate.', color=discord.Color(value=int(color, 16)))
        embed.set_author(name=f'{ctx.author}', icon_url=logo_url)
        embed.add_field(name='Reddit Thread', value=f'[Link]({thread_url})', inline=True)
        embed.add_field(name='Ump Sheet', value=f'[Link](https://docs.google.com/spreadsheets/d/{sheet_id})', inline=True)
        embed.add_field(name='AB Posted', value=swing_requested, inline=False)
        conditional_sub = '-'
        if conditional_swing_requested:
            conditional_sub = f'**Batter:** {robo_ump.get_player_name(conditional_batter)}\n'
            conditional_sub += f'**Notes:** {conditional_swing_notes}\n'
            conditional_sub += f'**Time:** {conditional_swing_requested}\n'
            if conditional_swing_src:
                conditional_sub += '**Swing**: On file'
            else:
                conditional_sub += '**Swing**: No swing on file'
        if swing_submitted:
            embed.add_field(name='Swing Posted', value=swing_submitted, inline=True)
        else:
            embed.add_field(name='Swing Posted', value='-', inline=True)
        embed.add_field(name='Conditional Sub', value=conditional_sub, inline=False)
        confirmation = await ctx.send(embed=embed, view=standard_buttons(self.ump_hq, embed, self.bot, league, season, session, game_id))

    @commands.command(brief='',
                      description='')
    async def request_auto_bb(self, ctx, team: str):
        season, session = robo_ump.get_current_session(team)
        league, season, session, game_id = robo_ump.fetch_game_team(team, season, session)
        game = robo_ump.fetch_game_team(team, season, session)
        thread_url, sheet_id = db.fetch_one('SELECT threadURL, sheetID FROM gameData WHERE league=%s AND season=%s AND session=%s AND gameID=%s', game)
        sql = '''SELECT pitch_requested, pitch_submitted, conditional_pitcher, conditional_pitch_requested, conditional_pitch_src, conditional_pitch_notes FROM pitchData WHERE league=%s AND season=%s AND session=%s AND game_id=%s'''
        pitch_requested, pitch_submitted, conditional_pitcher, conditional_pitch_requested, conditional_pitch_src, conditional_pitch_notes = db.fetch_one(sql, game)
        logo_url, color = db.fetch_one('SELECT logo_url, color FROM teamData WHERE abb=%s', (team,))

        embed = discord.Embed(title='Auto BB Request',
                              description=f'{ctx.author.mention} has requested an auto BB. Please investigate.',
                              color=discord.Color(value=int(color, 16)))
        embed.set_author(name=f'{ctx.author}', icon_url=logo_url)
        embed.add_field(name='Reddit Thread', value=f'[Link]({thread_url})', inline=True)
        embed.add_field(name='Ump Sheet', value=f'[Link](https://docs.google.com/spreadsheets/d/{sheet_id})',
                        inline=True)
        embed.add_field(name='Pitch Requested', value=pitch_requested, inline=False)
        conditional_sub = '-'
        if conditional_pitch_requested:
            conditional_sub = f'**Pitcher:** {robo_ump.get_player_name(conditional_pitcher)}\n'
            conditional_sub += f'**Notes:** {conditional_pitch_notes}\n'
            conditional_sub += f'**Time:** {conditional_pitch_requested}\n'
            if conditional_pitch_src:
                conditional_sub += '**Pitch**: On file'
            else:
                conditional_sub += '**Pitch**: No swing on file'
        if pitch_submitted:
            embed.add_field(name='Pitch Submitted', value=pitch_submitted, inline=True)
        else:
            embed.add_field(name='Pitch Submitted', value='-', inline=True)
        embed.add_field(name='Conditional Sub', value=conditional_sub, inline=False)
        confirmation = await ctx.send(embed=embed, view=standard_buttons(self.ump_hq, embed, self.bot, league, season, session, game_id))

    @commands.command(brief='',
                      description='')
    async def game_state(self, ctx, team: str):
        season, session = robo_ump.get_current_session(team)
        game = robo_ump.fetch_game_team(team, season, session)
        if game:
            sql = '''SELECT sheetID, awayTeam, homeTeam, awayScore, homeScore, inning, outs, obc, complete, threadURL, winningPitcher, losingPitcher, save, potg, state FROM gameData WHERE league=%s AND season=%s AND session=%s AND gameID=%s'''
            sheet_id, awayTeam, homeTeam, awayScore, homeScore, inning, outs, obc, complete, threadURL, winningPitcher, losingPitcher, save, potg, state = db.fetch_one(sql, game)
            sql = '''SELECT current_pitcher, current_batter, pitch_requested, pitch_submitted, pitch_src, swing_requested, swing_submitted, swing_src, conditional_pitch_requested, conditional_pitch_src, conditional_swing_requested, conditional_swing_src FROM pitchData WHERE league=%s AND season=%s AND session=%s AND game_id=%s'''
            current_pitcher, current_batter, pitch_requested, pitch_submitted, pitch_src, swing_requested, swing_submitted, swing_src, conditional_pitch_requested, conditional_pitch_src, conditional_swing_requested, conditional_swing_src = db.fetch_one(sql, game)
            color, logo = db.fetch_one('''SELECT color, logo_url FROM teamData WHERE abb=%s''', (team,))
            color = discord.Color(value=int(color, 16))
            title = f'{game[0].upper()} {game[1]}.{game[2]} | {awayTeam} vs. {homeTeam}'
            if state in ['SETUP', 'WAITING FOR LINEUPS']:
                description = f'{awayTeam: <4} {awayScore: <2}     ○     T1\n'
                description += f'{homeTeam: <4} {homeScore: <2}   ○   ○   {outs} Out'
                embed = discord.Embed(title=title, description=f'```{description}```', color=color, url=threadURL)

            elif state in ['WAITING FOR PITCH', 'WAITING FOR SWING', 'WAITING FOR RESULT', 'SUB REQUESTED', 'AUTO REQUESTED', 'WAITING FOR PITCH CONFIRMATION', 'WAITING FOR UMP CONFIRMATION']:
                matchup_names = sheets.read_sheet(sheet_id, assets.calc_cell2['current_matchup'])
                matchup_info = sheets.read_sheet(sheet_id, assets.calc_cell2['matchup_info'])
                if matchup_names:
                    batter_name = matchup_names[0][0]
                    pitcher_name = matchup_names[0][2]
                else:
                    return None
                if matchup_info:
                    batter_id, batter_type, batter_hand, pitcher_id, pitcher_type, pitcher_hand, pitcher_bonus = matchup_info[0]
                else:
                    return None

                # Setting up OBC text
                b1 = '○'
                b2 = '○'
                b3 = '○'
                if obc in [1, 4, 5, 7]:
                    b1 = '●'
                if obc in [2, 4, 6, 7]:
                    b2 = '●'
                if obc in [3, 5, 6, 7]:
                    b3 = '●'

                # Shorten names to last name only if longer than 15 characters
                while len(batter_name) > 15:
                    batter_name = batter_name.split(' ', 1)
                    if len(batter_name) > 1:
                        batter_name = batter_name[1]
                    else:
                        continue

                while len(pitcher_name) > 15:
                    pitcher_name = pitcher_name.split(' ', 1)
                    if len(pitcher_name) > 1:
                        pitcher_name = pitcher_name[1]
                    else:
                        continue

                description = f'{pitcher_name: <15}  {pitcher_hand[0]}|{pitcher_type}-{pitcher_bonus}\n'
                description += f'{batter_name: <15}  {batter_hand[0]}|{batter_type}\n\n'
                description += f'{awayTeam: <4} {awayScore: <2}     {b2}        {inning}\n'
                description += f'{homeTeam: <4} {homeScore: <2}   {b1}   {b3}   {outs} Out'
                embed = discord.Embed(title=title, description=f'```{description}```', color=color, url=threadURL)

                if pitch_requested:
                    if pitch_src:
                        embed.add_field(name='Pitch', value=f'Pitch submitted at {pitch_submitted}', inline=True)
                    else:
                        embed.add_field(name='Pitch', value=f'Pitch request sent at {pitch_requested}', inline=True)
                else:
                    embed.add_field(name='Pitch', value='-', inline=True)
                if swing_requested:
                    if swing_src:
                        embed.add_field(name='Swing', value=f'Swing submitted at {swing_submitted}', inline=True)
                    else:
                        embed.add_field(name='Swing', value=f'AB posted at {swing_requested}', inline=True)
                else:
                    embed.add_field(name='Swing', value='-', inline=True)
                if conditional_pitch_requested:
                    if conditional_pitch_src:
                        embed.add_field(name='Conditional Pitch', value='Conditional pitch submitted', inline=False)
                    else:
                        embed.add_field(name='Conditional Pitch', value='Waiting for pitch', inline=False)
                else:
                    embed.add_field(name='Conditional Pitch', value='-', inline=False)
                if conditional_swing_requested:
                    if conditional_swing_src:
                        embed.add_field(name='Conditional Swing', value='Conditional swing submitted', inline=True)
                    else:
                        embed.add_field(name='Conditional Swing', value='Waiting for swing', inline=True)
                else:
                    embed.add_field(name='Conditional Swing', value='-', inline=True)
            elif state in ['FINALIZING', 'COMPLETE']:
                description = f'{awayTeam: <4} {awayScore: <2}     ○     Final\n'
                description += f'{homeTeam: <4} {homeScore: <2}   ○   ○   '
                embed = discord.Embed(title=title, description=f'```{description}```', color=color, url=threadURL)
                if complete:
                    embed.add_field(name='Winning Pitcher', value=robo_ump.get_player_name(winningPitcher), inline=True)
                    embed.add_field(name='Losing Pitcher', value=robo_ump.get_player_name(losingPitcher), inline=True)
                    if save:
                        embed.add_field(name='Save', value=robo_ump.get_player_name(save), inline=True)
                    embed.add_field(name='Player of the Game', value=robo_ump.get_player_name(potg), inline=True)
            embed.set_thumbnail(url=logo)
            embed.add_field(name='Status', value=state.title())
            embed.add_field(name='View on Reddit', value=f'[Link]({threadURL})')
            await ctx.send(embed=embed)
        return

    @commands.command(brief='',
                      description='')
    async def check_swing(self, ctx, reddit_comment: str):
        await robo_ump.get_swing_from_reddit(reddit_comment)
        return

    @commands.command(brief='',
                      description='')
    async def do_result(self, ctx, team: str):
        season, session = robo_ump.get_current_session(team)
        league, season, session, game_id = robo_ump.fetch_game_team(team, season, session)
        pitch = await robo_ump.result(self.bot, league, season, session, game_id)
        await ctx.send(f'We did it reddit!')

    @commands.command(brief='',
                      description='')
    async def setup_games(self, ctx, session: int):
        await ctx.send(f'Setting up games for session {session}...')
        await robo_ump.create_ump_sheets(self.bot, session)
        await ctx.send('Done.')

    @commands.command(brief='',
                      description='')
    async def set_lineup(self, ctx, team: str):
        season, session = robo_ump.get_current_session(team)
        league, season, session, game_id = robo_ump.fetch_game_team(team, season, session)
        sheet_id = robo_ump.get_sheet(league, season, session, game_id)

        done = Button(label="Done", style=discord.ButtonStyle.green)
        cancel = Button(label="Cancel", style=discord.ButtonStyle.red)

        async def done_lineup(interaction):
            await interaction.response.edit_message(view=None)
            if robo_ump.lineup_check(sheet_id):
                matchup_info = sheets.read_sheet(sheet_id, assets.calc_cell2['matchup_info'])
                if matchup_info:
                    matchup_info = matchup_info[0]
                else:
                    return None
                db.update_database('UPDATE pitchData SET current_batter=%s, current_pitcher=%s WHERE league=%s AND season=%s AND session=%s AND game_id=%s', (matchup_info[0], matchup_info[3], league, season, session, game_id))
                robo_ump.set_state(league, season, session, game_id, 'WAITING FOR PITCH')
            else:
                await ctx.send('Still waiting for lineups.')
                await interaction.response.edit_message(view=None)
            return

        async def cancel_request(interaction):
            await interaction.response.edit_message(content='Request cancelled.', view=None)
            return

        cancel.callback = cancel_request
        done.callback = done_lineup
        view = View(timeout=None)
        view.add_item(done)
        view.add_item(cancel)

        await ctx.send(content=f'Here\'s your game sheet, please update the **Starting Lineups** tab.\nhttps://docs.google.com/spreadsheets/d/{sheet_id}', view=view)

    @commands.command(brief='',
                      description='')
    async def pause_game(self, ctx, team: str):
        season, session = robo_ump.get_current_session(team)
        league, season, session, game_id = robo_ump.fetch_game_team(team, season, session)
        robo_ump.log_msg(f'{datetime.datetime.now()} - {ctx.author.name} paused game {league} {season}.{session}.{game_id}')
        robo_ump.set_state(league, season, session, game_id, 'PAUSED')
        await ctx.message.add_reaction('👍')

    @commands.command(brief='',
                      description='')
    async def set_state(self, ctx, team: str, *, state: str):
        season, session = robo_ump.get_current_session(team)
        league, season, session, game_id = robo_ump.fetch_game_team(team, season, session)
        robo_ump.set_state(league, season, session, game_id, state.upper())
        await ctx.message.add_reaction('👍')


async def setup(bot):
    await bot.add_cog(Game(bot))


def standard_buttons(channel, embed, bot, league, season, session, game_id):
    confirm = Button(label="Confirm", style=discord.ButtonStyle.green)
    cancel = Button(label="Cancel", style=discord.ButtonStyle.red)

    async def send_request(interaction):
        if 'Auto' in embed.title:
            await channel.send(embed=embed, view=robo_ump.auto_buttons(bot, embed, league, season, session, game_id))
        else:
            await channel.send(embed=embed)
        await interaction.response.edit_message(content='Request sent.', view=None, embed=None)

    async def cancel_request(interaction):
        await interaction.response.edit_message(content='Request cancelled.', view=None, embed=None)
        return

    confirm.callback = send_request
    cancel.callback = cancel_request
    view = View(timeout=None)
    view.add_item(confirm)
    view.add_item(cancel)
    return view


