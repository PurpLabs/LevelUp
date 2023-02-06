import discord
from discord.ext import commands
from discord.commands import Option
from discord.ext.commands import MissingPermissions
import aiosqlite
import os
import random
import asyncio
from easy_pil import *

intents = discord.Intents.all()
bot = commands.Bot(intents=intents)

@bot.event
async def on_ready():
    print("Bot Ready")
    await bot.change_presence(activity=discord.Game("/botinfo"))
    setattr(bot, "db", await aiosqlite.connect("leveling.db"))
    await asyncio.sleep(3)
    async with bot.db.cursor() as cursor: 
        await cursor.execute("CREATE TABLE IF NOT EXISTS levels (level INTEGER, xp INTEGER, user INTEGER, guild INTEGER)")
        await cursor.execute("CREATE TABLE IF NOT EXISTS levelSettings (levelsys BOOL, role INTEGER, levelreq INTEGER, guild INTEGER)")

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    author = message.author
    guild = message.guild
    async with bot.db.cursor() as cursor:
        await cursor.execute("SELECT levelsys FROM levelSettings WHERE guild = ?", (guild.id,))
        levelsys = await cursor.fetchone()
        if levelsys and not levelsys[0]:
            return
        await cursor.execute("SELECT xp FROM levels WHERE user = ? AND guild = ?", (author.id, guild.id,))
        xp = await cursor.fetchone()
        await cursor.execute("SELECT level FROM levels WHERE user = ? AND guild = ?", (author.id, guild.id,))
        level = await cursor.fetchone()

    if not xp or not level:
        await cursor.execute("INSERT INTO levels (level, xp, user, guild) VALUES (?, ?, ?, ?)", (0, 0, author.id, guild.id,))
        
    try:
        xp = xp[0]
        level = level[0]
    except TypeError:
        xp = 0
        level = 0

    if level < 5:
        xp += random.randint(1, 3)
        await cursor.execute("UPDATE levels SET xp = ? WHERE user = ? AND guild = ?", (xp, author.id, guild.id,))
    else:
        rand = random.randint(1, (level//4))
        if rand == 1:
            xp += random.randint(1, 3)
            await cursor.execute("UPDATE levels SET xp = ? WHERE user = ? AND guild = ?", (xp, author.id, guild.id,))
    if xp >= 100:
        level += 1
        await cursor.execute("SELECT role FROM levelSettings WHERE levelreq = ? AND guild = ?", (level, guild.id,))
        role = await cursor.fetchone()
        await cursor.execute("UPDATE levels SET level = ? WHERE user = ? AND guild = ?", (level, author.id, guild.id,))
        await cursor.execute("UPDATE levels SET xp = ? WHERE user = ? AND guild = ?", (0, author.id, guild.id,))
        if role:
            role = role[0]
            role = guild.get_role(role)
            try:
                await author.add_roles(role)
                await message.channel.send(f"{author.mention} leveled up! Level {level}. You earned the **{role.name}** role!")
            except discord.HTTPException:
                await message.channel.send(f"{author.mention} leveled up! Level {level}")
                await bot.db.commit()
                await bot.process_commands(message)

@bot.slash_command(name="add-rewards", description="Add role rewards")
@commands.has_permissions(manage_guild=True)
async def slvl_rewards(ctx, level: Option(int, description="The level", required=True), *, role: Option(discord.Role, description="The role to add rewards for", required=True)):
    async with bot.db.cursor() as cursor:
        await cursor.execute("SELECT levelsys FROM levelSettings WHERE guild = ?", (ctx.guild.id,))
        levelsys = await cursor.fetchone()
    if levelsys:
        if not levelsys[0] == 1:
            return await ctx.respond("Level system is disabled in this server", ephemeral=True)
        await cursor.execute("SELECT role FROM levelSettings WHERE role = ? AND guild = ?", (role.id, ctx.guild.id,))
        roleTF = await cursor.fetchone()
        await cursor.execute("SELECT levelreq FROM levelSettings WHERE levelreq = ? AND guild = ?", (level, ctx.guild.id,))
        levelTF = await cursor.fetchone()
        if roleTF or levelTF:
            return await ctx.respond("A role or level for that value already exists, try another value", ephemeral=True)
        await cursor.execute("INSERT INTO levelSettings VALUES (?, ?, ?, ?)", (True, role.id, level, ctx.guild.id))
        await bot.db.commit()
        await ctx.respond("Updated level role")

@slvl_rewards.error
async def slvl_rewardserror(ctx, error):
    if isinstance(error, MissingPermissions):
        await ctx.respond("You are missing the required permissions | `Manage Server`", ephemeral=True)

@bot.slash_command(name="level", description="Check your level")
async def level(ctx, member: Option(discord.Member, description="The member", required=False)):
    if member == None:
        member=ctx.author
    async with bot.db.cursor() as cursor:
        await cursor.execute("SELECT levelsys FROM levelSettings WHERE guild = ?", (ctx.guild.id,))
    levelsys = await cursor.fetchone()
    if levelsys and not levelsys[0]:
        return
    await cursor.execute("SELECT xp FROM levels WHERE user = ? AND guild = ?", (member.id, ctx.guild.id,))
    xp = await cursor.fetchone()
    await cursor.execute("SELECT level FROM levels WHERE user = ? AND guild = ?", (member.id, ctx.guild.id,))
    level = await cursor.fetchone()

    if not xp or not level:
        await cursor.execute("INSERT INTO levels (level, xp, user, guild) VALUES (?, ?, ?, ?)", (0, 0, member.id, ctx.guild.id,))

    try:
        xp = xp[0]
        level = level[0]
    except TypeError:
        xp = 0
        level = 0

    user_data = {
      "name": f"{member.name}#{member.discriminator}",
      "xp": xp,
      "level": level,
      "next_level_xp": 100,
      "percentage": xp,
    }

    background = Editor(Canvas((900, 300), color="#4a494a"))
    pfp = await load_image_async(str(member.avatar.url))
    prfl = Editor(pfp).resize((150, 150)).circle_image()

    poppins = Font.poppins(size=40)
    poppins_small = Font.poppins(size=30)

    card_right_shape = [(600, 0), (750, 300), (900, 300), (900, 0)]

    background.polygon(card_right_shape, color="#6b74c7")
    background.paste(prfl, (30, 30))

    background.rectangle((30, 220), width=650, height=40, color="#f1f1f1", radius=20)
    background.bar((30, 220), max_width=650, height=40, percentage=user_data["percentage"], color="#6b74c7", radius=20,)
    background.text((200, 40), user_data["name"], font=poppins, color="#f1f1f1")

    background.rectangle((200, 100), width=350, height=2, fill="#6b74c7")
    background.text(
      (200, 130),
      f"Level: {user_data['level']} - XP: {user_data['next_level_xp']}",
      font = poppins_small,
      color="#f1f1f1",
    )

    file = discord.File(fp=background.image_bytes, filename="level.png")
    await ctx.respond(file=file)


@bot.slash_command(name="system-enable", description="Enable the level system")
@commands.has_permissions(manage_guild=True)
async def slvl_enable(ctx):
    async with bot.db.cursor() as cursor:
        await cursor.execute("SELECT levelsys FROM levelSettings WHERE guild = ?", (ctx.guild.id,))
        levelsys = await cursor.fetchone()
    if levelsys:
        if levelsys[0]:
            return await ctx.respond("Level system already enabled", ephemeral=True)
        await cursor.execute("UPDATE levelSettings SET levelsys = ? WHERE guild = ?", (True, ctx.guild.id,))
    else:
        await cursor.execute("INSERT INTO levelSettings VALUES (?, ?, ?, ?)", (True, 0, 0, ctx.guild.id,))
        await ctx.respond("Level system enabled", ephemeral=False)
        await bot.db.commit()

@slvl_enable.error
async def slvl_enableerror(ctx, error):
    if isinstance(error, MissingPermissions):
        await ctx.respond("You are missing the required permissions | `Manage Server`", ephemeral=True)

@bot.slash_command(name="system-disable", description="Disable the level system")
@commands.has_permissions(manage_guild=True)
async def slvl_disable(ctx):
    async with bot.db.cursor() as cursor:
        await cursor.execute("SELECT levelsys FROM levelSettings WHERE guild = ?", (ctx.guild.id,))
        levelsys = await cursor.fetchone()
    if levelsys:
        if not levelsys[0]:
            return await ctx.respond("Level system already disabled", ephemeral=True)
        await cursor.execute("UPDATE levelSettings SET levelsys = ? WHERE guild = ?", (False, ctx.guild.id,))
    else:
        await cursor.execute("INSERT INTO levelSettings VALUES (?, ?, ?, ?)", (False, 0, 0, ctx.guild.id,))
        await ctx.respond("Level system disabled", ephemeral=False)
        await bot.db.commit()

@slvl_disable.error
async def slvl_disableerror(ctx, error):
    if isinstance(error, MissingPermissions):
        await ctx.respond("You are missing the required permissions | `Manage Server`", ephemeral=True)
  
@bot.slash_command(name="ping", description="Check the bot's API latency")
async def ping(ctx):
    await ctx.respond(f"API latency: {round(bot.latency * 1000)}ms")

@bot.slash_command(name="botinfo", description="Information about the bot")
async def botinfo(ctx):
    embed=discord.Embed(
    title="Bot Info",
    description="LevelUp is a Discord leveling bot, you can use its powerful system to make your members active and chat for rewards!\n\nThe leveling system is already enabled when the bot gets invited to the server. To disable the system use the /system-disable command"
  )
    await ctx.respond(embed=embed)

@bot.slash_command(name="leaderboard", description="See the server's most active members")
async def leaderboard(ctx):
    async with bot.db.cursor() as cursor:
        await cursor.execute("SELECT levelsys FROM levelSettings WHERE guild = ?", (ctx.guild.id,))
        levelsys = await cursor.fetchone()
    if levelsys:
        if not levelsys[0]:
            return await ctx.respond("Level system already disabled", ephemeral=True)
        await cursor.execute("SELECT level, xp, user FROM levels WHERE guild = ? ORDER BY level DESC, xp DESC LIMIT 10", (ctx.guild.id,))
        data = await cursor.fetchall()
        if data:
            em = discord.Embed(title=f"{ctx.guild.name} Leaderboard")
            count = 0
            for table in data:
                count += 1
                user = ctx.guild.get_member(table[2])
                em.add_field(name=f"{count}. {user.name}", value=f"Level: `{table[0]}` | XP: `{table[1]}`", inline=False)
                return await ctx.respond(embed=em)

bot.run("")
