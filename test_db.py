import asyncio
import asyncpg


async def test_connection():
    try:
        conn = await asyncpg.connect('postgresql://hackathon_user:hackathon_pass@localhost:5433/hackathon_db')
        result = await conn.fetchval('SELECT version()')
        print('✅ Database connection successful!')
        print('Database version:', result)

        # Test our initialization script
        config_result = await conn.fetchval('SELECT value FROM hackathon.app_config WHERE key = $1', 'app_name')
        print('App name from config:', config_result)

        await conn.close()

    except Exception as e:
        print('❌ Database connection failed:', e)

if __name__ == '__main__':
    asyncio.run(test_connection())
