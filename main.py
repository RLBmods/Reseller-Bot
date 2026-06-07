import os
import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
RLB_API_KEY = os.getenv("RLB_API_KEY")
ADMIN_ROLE_ID = int(os.getenv("ADMIN_ROLE_ID", 0))
ALLOWED_GUILD_ID = int(os.getenv("ALLOWED_GUILD_ID", 0))
BASE_URL = "https://rlbmods.com/api/reseller"

TARGET_GUILD = discord.Object(id=ALLOWED_GUILD_ID)

class ResellerBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        
        super().__init__(command_prefix="!", intents=intents)
        self.raw_api_cache = []
        self.cached_products = []

    async def setup_hook(self):
        self.loop.create_task(self.initialize_bot_data())

    async def initialize_bot_data(self):
        """Handles syncing and caching background routines safely after gateway connection."""
        await self.wait_until_ready()
        await self.refresh_product_cache()
        
        try:
            self.tree.copy_global_to(guild=TARGET_GUILD)
            await self.tree.sync(guild=TARGET_GUILD)
            print(f"Slash commands synced instantly and strictly to Guild ID: {ALLOWED_GUILD_ID}")
        except discord.errors.HTTPException as e:
            print(f"[WARNING] Discord slash command sync was throttled or delayed: {e}")

    async def refresh_product_cache(self):
        """Fetches products from the API and stores their names/pricing maps in memory."""
        headers = {
            "Authorization": f"Bearer {RLB_API_KEY}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(f"{BASE_URL}/products", headers=headers) as response:
                    if response.status == 200:
                        try:
                            data = await response.json()
                            products_list = data if isinstance(data, list) else data.get("products", [])
                            
                            self.raw_api_cache = [prod for prod in products_list if isinstance(prod, dict)]
                            self.cached_products = [prod["name"] for prod in self.raw_api_cache if "name" in prod]
                            print(f"Product cache successfully updated: {self.cached_products}")
                        except Exception:
                            print("Failed to parse product cache JSON.")
                    else:
                        raw_err = await response.text()
                        print(f"Failed to update product cache. HTTP {response.status}: {raw_err[:100]}")
            except Exception as e:
                print(f"Connection error occurred during product cache updates: {e}")

bot = ResellerBot()

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name} (ID: {bot.user.id})")
    print("Bot is fully active and listening for slash commands...")
    print("--------------------------------------------------")

@bot.event
async def on_app_command_completion(interaction: discord.Interaction, command: app_commands.Command):
    print(f"[LOG] {interaction.user.name} successfully executed: /{command.name}")


def is_admin():
    """Validates if the invocation originates from the configured server and user role."""
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.guild_id != ALLOWED_GUILD_ID:
            embed = discord.Embed(
                title="⛔ System Lockdown",
                description="This bot is not authorized to execute operations within this server context.",
                color=discord.Color.dark_red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return False

        role = interaction.guild.get_role(ADMIN_ROLE_ID)
        if role and role in interaction.user.roles:
            return True
        
        embed = discord.Embed(
            title="⛔ Permission Denied",
            description="You do not possess the designated Admin role to use this command.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return False
    return app_commands.check(predicate)

async def handle_api_request(method: str, endpoint: str, json_data: dict = None, params: dict = None):
    """Handles HTTP requests safely and converts structural anomalies."""
    headers = {
        "Authorization": f"Bearer {RLB_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    url = f"{BASE_URL}{endpoint}"
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.request(method, url, headers=headers, json=json_data, params=params) as response:
                raw_text = await response.text()
                
                try:
                    data = await response.json()
                except Exception:
                    return {"success": False, "message": f"Server Error (HTTP {response.status}): {raw_text[:120]}"}

                if isinstance(data, list):
                    if response.status in [200, 201]:
                        return {"success": True, "data": data}
                    return {"success": False, "message": f"API returning raw array on error code {response.status}"}

                if isinstance(data, dict):
                    if response.status in [200, 201] or data.get("success") is True:
                        return {"success": True, "data": data}
                    
                    error_msg = data.get("error", {}).get("message") if isinstance(data.get("error"), dict) else data.get("message")
                    return {"success": False, "message": error_msg or f"HTTP Error {response.status}"}
                
                return {"success": False, "message": f"Unexpected structural layout received (HTTP {response.status})"}
                
        except Exception as e:
            return {"success": False, "message": f"Network gateway exception: {str(e)}"}


async def product_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    """Generates matching options inside the product selection field."""
    return [
        app_commands.Choice(name=prod, value=prod)
        for prod in bot.cached_products
        if current.lower() in prod.lower()
    ][:25]

async def duration_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    """Inspects the selected product context dynamically to output matching live duration plans."""
    product_choice = interaction.namespace.product
    if not product_choice:
        return [app_commands.Choice(name="⚠️ Please select a product first", value="invalid")]

    target_prod = next((p for p in bot.raw_api_cache if p.get("name") == product_choice), None)
    if not target_prod or "prices" not in target_prod:
        return [app_commands.Choice(name="❌ No available durations found", value="invalid")]

    choices = []
    prices = target_prod.get("prices", [])
    if isinstance(prices, list):
        for p in prices:
            if not isinstance(p, dict):
                continue
            
            dur_val = p.get("duration", "1")
            dur_type = str(p.get("duration_type", "days")).lower().strip()
            
            if "lifetime" in dur_type:
                label = "Lifetime Plan"
                api_value = f"{dur_val}|lifetime"
            else:
                unit = dur_type.rstrip('s') if int(dur_val) == 1 else dur_type
                label = f"{dur_val} {unit}"
                api_value = f"{dur_val}|{dur_type}"
                
            if current.lower() in label.lower():
                choices.append(app_commands.Choice(name=label, value=api_value))
                
    return choices[:25]


@bot.tree.command(name="balance", description="Check your reseller wallet balance.")
@is_admin()
async def balance(interaction: discord.Interaction):
    await interaction.response.defer()
    result = await handle_api_request("GET", "/balance")
    
    if not result["success"]:
        embed = discord.Embed(title="❌ Error Fetching Balance", description=result["message"], color=discord.Color.red())
        return await interaction.followup.send(embed=embed)
        
    data = result["data"]
    embed = discord.Embed(title="💰 Wallet Balance", color=discord.Color.green())
    embed.add_field(name="Current Balance", value=f"**{data.get('balance', '0.00')} {data.get('currency', 'USD')}**", inline=False)
    await interaction.followup.send(embed=embed)


@bot.tree.command(name="products", description="List available products and pricing structures.")
@is_admin()
async def products(interaction: discord.Interaction):
    await interaction.response.defer()
    
    result = await handle_api_request("GET", "/products")
    if not result["success"]:
        embed = discord.Embed(title="❌ Error Fetching Products", description=result["message"], color=discord.Color.red())
        return await interaction.followup.send(embed=embed)

    embed = discord.Embed(title="📦 Available Products & Pricing", color=discord.Color.blue())
    products_list = result["data"]
    
    if isinstance(products_list, dict):
        products_list = products_list.get("products", [])
    
    if not isinstance(products_list, list) or not products_list:
        embed.description = "No active products returned from reseller panel."
    else:
        for prod in products_list:
            if not isinstance(prod, dict):
                continue
                
            price_lines = []
            prices = prod.get("prices", [])
            if isinstance(prices, list):
                for price in prices:
                    if isinstance(price, dict):
                        dur_val = price.get('duration', '1')
                        dur_type = str(price.get('duration_type', 'days')).lower().strip()
                        if "lifetime" in dur_type:
                            price_lines.append(f"• Lifetime: **${price.get('price', '0.00')}**")
                        else:
                            unit = dur_type.rstrip('s') if int(dur_val) == 1 else dur_type
                            price_lines.append(f"• {dur_val} {unit}: **${price.get('price', '0.00')}**")
            
            pricing_text = "\n".join(price_lines) if price_lines else "No pricing configuration established."
            field_name = prod.get('name', 'Unknown Product')
            field_desc = f"*{prod.get('description', 'No description available.')}*\n{pricing_text}"
            
            embed.add_field(name=field_name, value=field_desc, inline=False)
            
    if isinstance(products_list, list):
        bot.raw_api_cache = [p for p in products_list if isinstance(p, dict)]
        bot.cached_products = [p["name"] for p in bot.raw_api_cache if "name" in p]
        
    await interaction.followup.send(embed=embed)


@bot.tree.command(name="status", description="List real-time product operational statuses.")
@is_admin()
async def status(interaction: discord.Interaction):
    await interaction.response.defer()
    
    result = await handle_api_request("GET", "/status")
    if not result["success"]:
        embed = discord.Embed(title="❌ Error Fetching Statuses", description=result["message"], color=discord.Color.red())
        return await interaction.followup.send(embed=embed)
        
    data = result["data"]
    statuses_list = data.get("statuses", []) if isinstance(data, dict) else data
    
    embed = discord.Embed(title="🖥️ Software Operational Status", color=discord.Color.teal())
    
    if not isinstance(statuses_list, list) or not statuses_list:
        embed.description = "No structural status data currently documented."
    else:
        for item in statuses_list:
            if not isinstance(item, dict):
                continue
            
            raw_status = str(item.get("status", "")).lower().strip()
            if "undetect" in raw_status:
                status_emoji = "🟢 Undetected"
            elif "auto-update" in raw_status:
                status_emoji = "🟢 Auto-updates"
            elif "updat" in raw_status:
                status_emoji = "🟡 Updating"
            elif "test" in raw_status:
                status_emoji = "¼ Testing"
            elif "detect" in raw_status:
                status_emoji = "🔴 Detected"
            elif "risk" in raw_status or "own risk" in raw_status:
                status_emoji = "⚠️ Use at own risk"
            else:
                status_emoji = f"⚪ {item.get('status', 'Unknown')}"
                
            embed.add_field(
                name=f"{item.get('name', 'Unknown')}",
                value=f"**Game:** {item.get('game', 'N/A')}\n**Status:** {status_emoji}\n*Last Updated: {item.get('updated_at', 'N/A')}*",
                inline=True
            )
            
    await interaction.followup.send(embed=embed)


@bot.tree.command(name="keys", description="List purchased keys. Optionally filter by product.")
@app_commands.describe(product="Select a product from the dynamic list to filter items")
@app_commands.autocomplete(product=product_autocomplete)
@is_admin()
async def keys(interaction: discord.Interaction, product: str = None):
    await interaction.response.defer()
    
    params = {"product": product} if product else None
    result = await handle_api_request("GET", "/keys", params=params)
    
    if not result["success"]:
        embed = discord.Embed(title="❌ Error Fetching Keys", description=result["message"], color=discord.Color.red())
        return await interaction.followup.send(embed=embed)
        
    keys_list = result["data"]
    if isinstance(keys_list, dict):
        keys_list = keys_list.get("keys", [])

    embed = discord.Embed(title="🔑 Purchased License Keys", color=discord.Color.purple())
    
    if not isinstance(keys_list, list) or not keys_list:
        embed.description = f"No keys found matching configuration requests{f' for product: {product}' if product else ''}."
    else:
        for item in keys_list[:10]:
            if not isinstance(item, dict):
                continue
            status_emoji = "🟢" if str(item.get("status")).lower() == "active" else "⚪"
            embed.add_field(
                name=f"{status_emoji} `{item.get('license_key', 'UNKNOWN-KEY')}`",
                value=f"**Product:** {item.get('product_name', 'N/A')}\n**Expires:** {item.get('expires_at', 'N/A')}",
                inline=True
            )
        if len(keys_list) > 10:
            embed.set_footer(text=f"Showing top 10 out of {len(keys_list)} total keys.")

    await interaction.followup.send(embed=embed)


@bot.tree.command(name="purchase", description="Generate and purchase new license keys.")
@app_commands.describe(
    product="Select product package from dropdown",
    duration="Select the exact duration option built for this product",
    count="Number of separate keys to purchase (Max: 50)"
)
@app_commands.autocomplete(product=product_autocomplete, duration=duration_autocomplete)
@is_admin()
async def purchase(interaction: discord.Interaction, product: str, duration: str, count: int = 1):
    await interaction.response.defer()
    
    if duration == "invalid" or "|" not in duration:
        embed = discord.Embed(title="❌ Purchase Aborted", description="Please select an operational duration layout choice from the autocomplete options.", color=discord.Color.red())
        return await interaction.followup.send(embed=embed)

    parsed_duration, parsed_duration_type = duration.split("|", 1)
    
    payload = {
        "product": product,
        "duration": int(parsed_duration),
        "duration_type": parsed_duration_type,
        "count": count
    }
    
    result = await handle_api_request("POST", "/keys/create", json_data=payload)
    if not result["success"]:
        embed = discord.Embed(title="❌ Purchase Failed", description=result["message"], color=discord.Color.red())
        return await interaction.followup.send(embed=embed)
        
    data = result["data"]
    embed = discord.Embed(title="✅ Keys Generated Successfully", color=discord.Color.gold())
    embed.description = data.get("message", "Operation processed successfully.")
    
    generated_keys = data.get("keys", [])
    if isinstance(generated_keys, list):
        keys_str = "\n".join([f"`{k}`" for k in generated_keys])
    else:
        keys_str = f"`{generated_keys}`" if generated_keys else "No keys returned."
    
    embed.add_field(name="Generated Keys", value=keys_str, inline=False)
    embed.add_field(name="Cost Deducted", value=f"${data.get('cost', '0.00')}", inline=True)
    embed.add_field(name="New Balance", value=f"${data.get('new_balance', '0.00')}", inline=True)
    
    await interaction.followup.send(embed=embed)


@bot.tree.command(name="reset_hwid", description="Reset HWID lock status data for a specified license key.")
@app_commands.describe(product="Select target product association", license_key="Paste key alphanumeric value string")
@app_commands.autocomplete(product=product_autocomplete)
@is_admin()
async def reset_hwid(interaction: discord.Interaction, product: str, license_key: str):
    await interaction.response.defer()
    
    payload = {
        "product": product,
        "license_key": license_key
    }
    
    result = await handle_api_request("POST", "/keys/reset", json_data=payload)
    if not result["success"]:
        embed = discord.Embed(title="❌ HWID Reset Failed", description=result["message"], color=discord.Color.red())
        return await interaction.followup.send(embed=embed)
        
    data = result["data"]
    embed = discord.Embed(
        title="🔄 HWID Reset Success", 
        description=data.get("message", "Hardware profile records wiped completely."), 
        color=discord.Color.green()
    )
    embed.add_field(name="Product", value=product, inline=True)
    embed.add_field(name="Key Targeted", value=f"`{license_key}`", inline=True)
    
    await interaction.followup.send(embed=embed)




@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CheckFailure):
        return
    
    embed = discord.Embed(
        title="⚠️ Execution Error", 
        description=f"An unhandled backend process error surfaced: {str(error)}", 
        color=discord.Color.dark_red()
    )
    if interaction.response.is_done():
        await interaction.followup.send(embed=embed)
    else:
        await interaction.response.send_message(embed=embed, ephemeral=True)

if __name__ == "__main__":
    bot.run(TOKEN)