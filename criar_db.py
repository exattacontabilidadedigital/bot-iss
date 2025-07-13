import sqlite3

def save_to_database(dados):
    """Salva dados no banco SQLite com substituição de duplicados"""
    try:
        # Abrir conexão com o banco usando 'with' para garantir que a conexão seja fechada corretamente
        with sqlite3.connect('empresas.db') as conn:
            c = conn.cursor()
            
            # Criar a tabela se não existir
            c.execute('''CREATE TABLE IF NOT EXISTS empresas (
                im TEXT, 
                cnpj TEXT UNIQUE,
                nome TEXT, 
                omisso TEXT, 
                debito TEXT
            )''')
            
            # Inserir os dados, substituindo os duplicados
            c.executemany('INSERT OR REPLACE INTO empresas (im, cnpj, nome, omisso, debito) VALUES (?, ?, ?, ?, ?)', dados)
            
            # Commit para garantir a gravação dos dados
            conn.commit()
            print(f"📊 {len(dados)} registros salvos com sucesso no banco.")
    
    except sqlite3.Error as e:
        print(f"Erro ao salvar no banco de dados: {e}")

if __name__ == "__main__":
    # Exemplo de dados a serem inseridos
    dados = [
        ("1234567890", "35496100000135", "Exatta Contabilidade Digital LTDA ", "Sim", "sim"),
        ("2345678901", "11.111.111/0001-92", "Outra Empresa", "Sim", "Não")
    ]
    
    # Chamar a função para salvar os dados
    save_to_database(dados)