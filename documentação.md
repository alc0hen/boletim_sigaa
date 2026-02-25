# Documentação do Boletim App

Este documento descreve a estrutura, APIs e pontos importantes do projeto Boletim App.

## Visão Geral

O Boletim App é uma aplicação Flask que atua como interface para o sistema acadêmico SIGAA, permitindo aos alunos visualizar notas, frequência e histórico de forma otimizada. Suporta múltiplas instituições (IFAL, UFAL) através de um padrão Strategy.

## Estrutura do Projeto

- `app/`: Código fonte da aplicação.
  - `routes.py`: Definição das rotas e endpoints da API.
  - `models.py`: Modelos de banco de dados (User, LinkedAccount).
  - `sigaa_api/`: Módulo de interação com o SIGAA (Scraping/API).
  - `domain/`: Lógica de negócio (Cálculo de notas, Factories).
  - `templates/`: Arquivos HTML (Jinja2).
  - `static/`: Arquivos CSS e JS.
- `run.py`: Ponto de entrada da aplicação.

## API e Rotas Importantes

### Autenticação
- `/login`: Rota de login principal. Suporta POST com `username`, `password` e `institution`.
- `/login/google`: Inicia o fluxo OAuth com Google.
- `/logout`: Encerra a sessão.

### Dashboard e Funcionalidades
- `/dashboard`: Painel principal. Renderiza o `dashboard.html`.
- `/profile`: Gerenciamento de contas vinculadas e perfil.
- `/api/stream_grades`: **Endpoint Sensível**. Retorna um stream de eventos (Server-Sent Events style, mas NDJSON) com os dados das disciplinas em tempo real. Utiliza as credenciais da sessão para fazer scraping no SIGAA.
- `/api/update_course/<id>`: Atualiza os dados de uma disciplina específica.
- `/api/academic_profile`: Retorna o histórico escolar completo (notas passadas).

### Demo
- `/demo`: Versão de demonstração com dados fictícios.
- `/api/stream_demo`: Endpoint de stream para o modo demo.

## Segurança e Pontos Sensíveis

1.  **Credenciais**: As senhas do SIGAA são armazenadas de forma criptografada no banco de dados (`LinkedAccount`) para permitir a atualização automática em segundo plano. O `LinkedAccount.get_password()` descriptografa quando necessário.
2.  **SSRF Protection**: O módulo `sigaa_api` implementa proteções contra Server-Side Request Forgery ao validar URLs de redirecionamento.
3.  **Sessão**: A sessão do Flask armazena cookies do SIGAA (`sigaa_cookies`) para manter a conexão ativa durante a navegação.
4.  **Cache**: Dados históricos são cacheados criptografados no banco para evitar requisições desnecessárias ao SIGAA.

## Variáveis de Ambiente

O sistema depende de variáveis de ambiente para configuração (ex: `SECRET_KEY`, `DATABASE_URL`, credenciais do Google OAuth). Em produção, certifique-se de que estas estejam definidas corretamente.
