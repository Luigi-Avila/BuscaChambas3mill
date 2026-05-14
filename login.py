import asyncio
from playwright.async_api import async_playwright
import os

async def login_linkedin():
    """
    Opens a browser to let the user log into LinkedIn manually.
    The session is saved in the '.linkedin_session' directory.
    """
    user_data_dir = os.path.join(os.getcwd(), ".linkedin_session")
    
    if not os.path.exists(user_data_dir):
        os.makedirs(user_data_dir)
        print(f"Created session directory: {user_data_dir}")

    async with async_playwright() as p:
        print("Launching browser for manual login...")
        # Launch persistent context
        context = await p.chromium.launch_persistent_context(
            user_data_dir,
            headless=False,  # Must be visible to log in
            args=["--start-maximized"]
        )
        
        page = context.pages[0] if context.pages else await context.new_page()
        
        print("Navigating to LinkedIn...")
        await page.goto("https://www.linkedin.com/login")
        
        print("\n" + "="*50)
        print("ACCION REQUERIDA:")
        print("1. Inicia sesión manualmente en la ventana del navegador.")
        print("2. Completa el 2FA si es necesario.")
        print("3. Una vez que veas tu Feed de LinkedIn, regresa aquí.")
        print("="*50 + "\n")
        
        input("Presiona ENTER en esta terminal cuando hayas terminado de loguearte para cerrar y guardar la sesión...")
        
        await context.close()
        print("Sesión guardada correctamente en '.linkedin_session'.")

if __name__ == "__main__":
    asyncio.run(login_linkedin())
