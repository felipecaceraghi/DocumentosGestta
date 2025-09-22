#!/usr/bin/env python3
# test_auth.py - Teste rápido de autenticação

import json
from api import get_token, get_all_companies, get_all_users

def test_authentication():
    print("🔐 Testando autenticação...")
    
    # Carregar credenciais
    try:
        with open('gestta_config.json', 'r') as f:
            config = json.load(f)
        
        email = config['credentials']['email']
        password = config['credentials']['password']
        
        print(f"📧 Email: {email}")
        print(f"🔑 Senha: {'*' * len(password)} ({len(password)} caracteres)")
        
        # Teste de login
        print("\n📡 Fazendo login...")
        token = get_token(email, password)
        
        if token:
            print("✅ Login realizado com sucesso!")
            print(f"🎫 Token obtido: {token[:50]}...")
            
            # Teste de busca de empresas
            print("\n🏢 Buscando empresas...")
            companies = get_all_companies(token)
            if companies:
                print(f"✅ {len(companies)} empresas carregadas!")
            else:
                print("❌ Nenhuma empresa encontrada")
            
            # Teste de busca de usuários
            print("\n👥 Buscando usuários...")
            users = get_all_users(token)
            if users:
                print(f"✅ {len(users)} usuários carregados!")
            else:
                print("❌ Nenhum usuário encontrado")
                
        else:
            print("❌ Falha no login!")
            
    except Exception as e:
        print(f"❌ Erro: {e}")

if __name__ == "__main__":
    test_authentication()