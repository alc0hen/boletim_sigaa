import asyncio
import os
import sys
from dotenv import load_dotenv
load_dotenv()
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from sigaa_api.sigaa import Sigaa, InstitutionType
async def main():
    username = os.getenv('SIGAA_USER')
    password = os.getenv('SIGAA_PASS')
    if not username or not password:
        print("Erro: Defina as variáveis de ambiente SIGAA_USER e SIGAA_PASS.")
        print("Exemplo: export SIGAA_USER=seu_usuario SIGAA_PASS=sua_senha")
        return
    print("Iniciando conexão com o SIGAA (IFAL)...")
    sigaa = Sigaa("https://sigaa.ifal.edu.br", InstitutionType.IFAL)
    try:
        print(f"Tentando login como {username}...")
        account = await sigaa.login(username, password)
        print("Login realizado com sucesso!")
        name = await account.get_name()
        print(f"Nome do Usuário: {name}")
        if not account.active_bonds:
            print("Nenhum vínculo ativo encontrado.")
            return
        print(f"Encontrados {len(account.active_bonds)} vínculos ativos.")
        for bond in account.active_bonds:
            print(f"\n--- Vínculo: {bond.program} ({bond.registration}) ---")
            print("Buscando matérias (turmas)...")
            courses = await bond.get_courses()
            if not courses:
                print("Nenhuma matéria encontrada neste vínculo.")
                continue
            for course in courses:
                print(f"\nMatéria: {course.title}")
                try:
                    print("  Buscando notas...")
                    grades = await course.get_grades()
                    if not grades:
                        print("  Sem notas lançadas.")
                    for grade in grades:
                        if grade['type'] == 'single':
                            val = grade['value'] if grade['value'] is not None else '-'
                            print(f"  - {grade['name']}: {val}")
                        elif grade['type'] == 'group':
                            print(f"  - {grade['name']}:")
                            for sub in grade.get('grades', []):
                                val = sub['value'] if sub.get('value') is not None else '-'
                                name = sub.get('name', 'Nota')
                                print(f"    * {name}: {val}")
                except Exception as e:
                    print(f"  Erro ao buscar notas: {e}")
    except Exception as e:
        print(f"Falha no login ou erro: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await sigaa.close()
if __name__ == "__main__":
    asyncio.run(main())
