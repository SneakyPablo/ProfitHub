class ProductPanel(discord.ui.View):
    def __init__(self, product_id: str):
        super().__init__(timeout=None)
        self.product_id = product_id

    @discord.ui.button(label="Buy Now", style=discord.ButtonStyle.green)
    async def buy_now(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Get the ticket manager cog
        ticket_manager = interaction.client.get_cog('TicketManager')
        if ticket_manager:
            await ticket_manager.create_ticket(interaction, self.product_id)
        else:
            await interaction.response.send_message(
                "Error: Ticket system is not available.", 
                ephemeral=True
            )

    @discord.ui.button(label="Request Info", style=discord.ButtonStyle.blue)
    async def request_info(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            product = await interaction.client.db.get_product(ObjectId(self.product_id))
            if product:
                embed = discord.Embed(
                    title=product['name'],
                    description=product['description'],
                    color=discord.Color.blue()
                )
                embed.add_field(name="Price", value=f"${product['price']}")
                if product.get('category'):
                    embed.add_field(name="Category", value=product['category'])
                await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(
                    "Product not found!", 
                    ephemeral=True
                )
        except Exception as e:
            await interaction.response.send_message(
                "Error fetching product information.", 
                ephemeral=True
            )
