# RFC — Desenho da API Bancária (Protótipo)

**TIME** `tea · zumbao`
**DATA** `26/09/2026`
**VERSÃO** `1`

---

> 💡 **Orientação Visual:**
> Durante o desenho e implementação destas etapas, **abusemos do uso de diagramas (especialmente Mermaid)**! O uso de esquemas visuais (como diagramas de sequência, Entidade-Relacionamento e fluxo) facilita imensamente a validação da lógica de negócio e o entendimento do projeto.

---

## 🏗️ FRENTE DE TRABALHO 1: Contexto e Modelo de Dados (Responsável: tea)

### Contextualização

#### Entendendo o problema
O sistema é um protótipo de banco digital que precisa oferecer operações financeiras básicas de forma segura e consistente, lidando com o desafio crítico de manter a integridade do dinheiro.
* **Operações oferecidas:** Cadastro e autenticação (login) de clientes, criação de contas, depósitos, transferências (PIX, TED, Internacional) com cobrança de tarifas, e geração de extrato.
* **Garantias em cima do dinheiro:** O sistema precisa garantir o princípio ACID. O dinheiro não pode ser criado (exceto por depósito), duplicado ou perdido. Se houver concorrência (várias transferências simultâneas) e der errado, podemos ter saldo divergente (negativo), transações duplicadas ou dinheiro trocando de mãos sem o devido bloqueio de registro.
* **Fora de escopo desta entrega:** Pix copia-e-cola, Boletos, Empréstimos e contas PJ (Pessoa Jurídica).

#### Explicando a solução de forma macro
A solução foi construída utilizando **Python com FastAPI, SQLAlchemy (ORM) e PostgreSQL**, rodando em contêineres **Docker**. A segurança e identificação dos usuários baseia-se exclusivamente em tokens JWT. Para garantir a integridade do dinheiro, o sistema deve utilizar controle transacional relacional para as operações de débito e crédito, isolando o estado da conta a cada requisição.

* `<Controle de saldo em memória / Python>` — Descartada porque causaria *Race Conditions* e deixaria saldos inconsistentes em um ambiente de concorrência real. Ganharia se a API fosse um sistema monolítico bloqueante operando em *single-thread*.

```mermaid
flowchart LR
    Cliente["🧑 Cliente HTTP"]

    subgraph Docker ["Docker Compose"]
        API["⚡ FastAPI
Python 3
Middleware JWT"]
        DB["🐘 PostgreSQL
Transações ACID
Check Constraints"]
    end

    Cliente -->|"HTTPS Request
Bearer Token"| API
    API -->|"SQLAlchemy ORM
SELECT / INSERT / UPDATE"| DB
    DB -->|"Linhas + Status"| API
    API -->|"JSON Response"| Cliente
```

### Banco de Dados (Somente diagrama)
*(Diagrama fiel ao modelo implementado no código. Tipos, restrições e relacionamentos refletem diretamente os modelos SQLAlchemy do projeto.)*

```mermaid
erDiagram
    CUSTOMER {
        int id PK "SERIAL - interno"
        char customer_key UK "CHAR-36 - UUID público"
        string name "VARCHAR-255"
        char document_number UK "CHAR-14 - CPF único"
        string email UK "VARCHAR-255 único"
        string password_hash "VARCHAR-255 - nunca texto plano"
        date birth_date
        int status_id FK
    }
    CUSTOMER_STATUS {
        int id PK
        string enumerator UK "created, pending, success, failed"
    }
    CUSTOMER_STATUS_EVENT {
        int id PK
        int customer_id FK
        int status_id FK
        datetime created_at
    }

    ACCOUNT {
        int id PK "SERIAL - interno"
        char account_key UK "CHAR-36 - UUID público"
        int customer_id FK
        string branch "VARCHAR-10"
        string number UK "branch+number únicos"
        string type "VARCHAR-20 checking ou savings"
        bigint balance "Em centavos. CHECK maior ou igual a 0"
        int status_id FK
    }
    ACCOUNT_STATUS {
        int id PK
        string enumerator UK "active, blocked, closed"
    }
    ACCOUNT_STATUS_EVENT {
        int id PK
        int account_id FK
        int status_id FK
        datetime created_at
    }

    TRANSACTION {
        int id PK "SERIAL - interno"
        char transaction_key UK "CHAR-36 - UUID público"
        int origin_account_id FK "NULL para depósito"
        int destination_account_id FK
        bigint amount "Em centavos"
        bigint fee_amount "Em centavos. Default 0"
        int fee_id FK
        string type "deposit ou transfer"
        string channel "pix, ted, card, international"
        int status_id FK
    }
    TRANSACTION_STATUS {
        int id PK
        string enumerator UK "pending, confirmed, failed"
    }
    TRANSACTION_STATUS_EVENT {
        int id PK
        int transaction_id FK
        int status_id FK
        datetime created_at
    }

    FEE {
        int id PK
        string type UK "pix, ted, card, international"
        numeric percentage "NUMERIC-5-2 ex: 5.00 ou 8.00"
    }

    CUSTOMER ||--o{ ACCOUNT : "possui"
    CUSTOMER }o--|| CUSTOMER_STATUS : "tem status"
    CUSTOMER ||--o{ CUSTOMER_STATUS_EVENT : "registra transição"
    CUSTOMER_STATUS_EVENT }o--|| CUSTOMER_STATUS : "mapeia para"

    ACCOUNT }o--|| ACCOUNT_STATUS : "tem status"
    ACCOUNT ||--o{ ACCOUNT_STATUS_EVENT : "registra transição"
    ACCOUNT_STATUS_EVENT }o--|| ACCOUNT_STATUS : "mapeia para"

    ACCOUNT ||--o{ TRANSACTION : "envia"
    ACCOUNT ||--o{ TRANSACTION : "recebe"
    TRANSACTION }o--|| TRANSACTION_STATUS : "tem status"
    TRANSACTION ||--o{ TRANSACTION_STATUS_EVENT : "registra transição"
    TRANSACTION_STATUS_EVENT }o--|| TRANSACTION_STATUS : "mapeia para"
    TRANSACTION }o--o| FEE : "usa tabela de tarifas"
```
### Decisões de Modelagem e Padrões de Banco de Dados

Para garantir a resiliência financeira, evitar perdas por precisão matemática e proteger a infraestrutura, o modelo de dados adota três padrões arquiteturais rigorosos:

#### 1. Dupla Identificação (Isolamento de IDs)
A exposição de chaves primárias sequenciais revela a volumetria do negócio e facilita ataques de enumeração. Por isso, todo registro no sistema possui duas formas de identificação:
*   **ID Interno (`SERIAL` / `INTEGER`):** Usado estritamente para as chaves estrangeiras e relacionamentos internos físicos dentro do banco de dados, garantindo alta performance nas buscas e *joins*.
*   **Chave Externa (`UUID`):** Identificador público (ex: `account_key`, `customer_key`), sendo o único valor exposto nos *endpoints* da API e URLs.

```mermaid
flowchart LR
    subgraph Mundo Externo API
        Req[Request: GET /accounts/a1b2c3d4...]
        DTO[Resposta HTTP: account_key: a1b2c3d4...]
    end
    
    subgraph Banco de Dados PostgreSQL
        Acc[Tabela: ACCOUNT\n id: 1042 SERIAL\n key: a1b2c3d4... UUID]
        Trans[Tabela: TRANSACTION\n origin_account_id: 1042]
        
        Acc --- Trans
    end

    Req -->|"Busca por UUID"| Acc
    Acc -->|"Mascarado no DTO"| DTO
```
#### 2. Matemática Inteira para Valores Monetários (Centavos)
O dinheiro no banco de dados não utiliza casas decimais (`FLOAT` ou `DECIMAL`), pois operações de ponto flutuante causam erros de precisão e arredondamento[cite: 2].   
* Todos os valores monetários (`amount`, `balance`) são salvos como inteiros (`BIGINT`), representando sempre os centavos da moeda[cite: 2].   
* No momento em que o JSON da requisição chega à API (ex: 100.0), o *controller* converte esse valor imediatamente para `int` antes de qualquer manipulação de regra de negócio[cite: 2].

#### 3. Rastreabilidade e Imutabilidade (Eventos de Status)
Em sistemas financeiros, o passado nunca é apagado[cite: 2]. Para garantir total rastreabilidade sobre o que aconteceu com uma transação, não sobrescrevemos o status anterior.
* **Enumeradores Estáticos:** Utilizamos tabelas de domínio estático (ex: `transaction_status`) para padronizar os estados possíveis, como 'pending' e 'confirmed'[cite: 2].
* **Tabelas de Eventos:** Cada mudança de status gera um novo registro em tabelas como `transaction_status_event`, criando uma linha do tempo exata e imutável para a vida de cada transação[cite: 2].

```mermaid
erDiagram
    TRANSACTION ||--o{ TRANSACTION_STATUS_EVENT : "registra transição de estado"
    TRANSACTION_STATUS_EVENT }o--|| TRANSACTION_STATUS : "mapeia para"

    TRANSACTION {
        int id PK "SERIAL"
        uuid transaction_key UK "UUID"
        bigint amount "Em centavos"
    }
    TRANSACTION_STATUS {
        int id PK
        string status_name UK "'pending', 'confirmed'"
    }
    TRANSACTION_STATUS_EVENT {
        int id PK
        int transaction_id FK
        int status_id FK
        datetime created_at
    }
```
#### 4. Máquina de Estados (Ciclo de Vida das Entidades)
Para refletir fielmente o domínio bancário, as entidades principais possuem um ciclo de vida restrito, controlado por campos de `status` no banco de dados[cite: 2]:
* **Conta (`ACCOUNT.status`):** Uma conta só pode enviar ou receber fundos se estiver **ativa**[cite: 2]. Contas com status **bloqueado ou encerrado** são rejeitadas imediatamente na camada de validação de negócios[cite: 2].
* **Transação (`TRANSACTION_STATUS`):** O ciclo de uma transação transita por estados padronizados. Toda transação nasce como **'pending'** e só avança para **'confirmed'** após o sucesso da execução atômica do banco de dados[cite: 2]. Falhas de saldo ou regras de negócio resultam em **'failed'**[cite: 2].

```mermaid
stateDiagram-v2
    direction LR
    [*] --> active : Conta criada
    active --> blocked : Bloqueio manual
    blocked --> active : Desbloqueio
    active --> closed : Encerramento com saldo zero
    blocked --> closed : Encerramento com saldo zero
    closed --> [*]
```

```mermaid
stateDiagram-v2
    direction LR
    [*] --> pending : Transação iniciada
    pending --> confirmed : COMMIT com sucesso
    pending --> failed : ROLLBACK por saldo insuficiente
    confirmed --> [*]
    failed --> [*]
```

#### 5. Segurança e Dados Sensíveis
O modelo de dados implementa proteções fundamentais para informações críticas:
* **Senhas:** A coluna `password_hash` na tabela `CUSTOMER` jamais armazena senhas em texto plano. Todo acesso deve utilizar algoritmos de *hashing* fortes (ex: Bcrypt ou Argon2).
* **Identidade Segura:** O modelo não confia em dados enviados no corpo da requisição para autorização[cite: 2]. A identificação do cliente para consultas e transferências depende única e exclusivamente do token JWT gerado e validado no middleware, extraindo o `customer_key` de forma segura[cite: 2].
---


## 🛤️ FRENTE DE TRABALHO 2: Rotas e Fluxos (Responsável: zumbao)

### Implementação

#### Rotas
| MÉTODO | CAMINHO | O QUE FAZ | ENTRADA (CAMPOS QUE IMPORTAM) | SAÍDAS (STATUS E QUANDO) |
| :--- | :--- | :--- | :--- | :--- |
| **POST** | `/customers/{key}/accounts` | Abre nova conta no perfil do cliente | `type` (checking ou savings) | **201:** Conta criada.<br>**401:** Faltou JWT na requisição.<br>**403:** Tentou abrir conta no perfil de outro cliente.<br>**422:** Cliente já possui 3 contas ativas ou enviou tipo inválido. |
| **GET** | `/accounts` | Lista contas do próprio cliente (Idempotente) | *Sem payload.* (A identidade vem do Header `JWT`) | **200:** Lista retornada com sucesso (nunca exibe contas de terceiros). *(Idempotente pois requisições repetidas não alteram estado e retornam a mesma lista se não houverem novas aberturas)* |
| **GET** | `/accounts/{key}` | Exibe detalhes de uma conta (Idempotente) | `key` (via Path) | **200:** Detalhes exibidos.<br>**403:** Conta não pertence ao cliente do JWT.<br>**404:** Conta inexistente.<br>*(Idempotente pois trata-se de leitura restrita)* |
| **POST** | `/transactions` | Efetua transferência ou depósito | `type` (pix, ted, deposit), `amount`, `destination_account_key` | **201:** Transação efetivada.<br>**403:** Tentativa de débito em conta origem de outro cliente.<br>**422:** Saldo insuficiente, valor inválido ou conta destino bloqueada/inexistente. |
| **GET** | `/accounts/{key}/statement` | Emite o extrato paginado (Idempotente) | `limit`, `page` | **200:** Extrato devolvido.<br>**403:** Tentou consultar extrato de outro cliente.<br>**400:** Data de início maior que a de fim, ou limitador inválido.<br>*(Idempotente pois paginação e filtros estáticos na URL sempre geram o mesmo recorte do histórico)* |

> **Nota de Segurança e Identidade:** O payload de `/transactions` **não** recebe a `origin_account_key`, e o extrato não aceita busca livre. A identidade do cliente que executa a operação é inferida **sempre** pelo token JWT (blindando vazamento horizontal).

#### Fluxos

**1. Fluxo Lógico de Abertura de Conta**
Este fluxo ilustra a regra de negócio para limitação de contas, avaliando o limite de 3 contas ativas por perfil:

```mermaid
sequenceDiagram
    actor Cliente
    participant API as FastAPI
    participant DB as PostgreSQL
    
    Cliente->>API: POST /customers/{key}/accounts (type)
    API->>API: Verifica se JWT == {key} da URL
    alt Identidade diverge
        API-->>Cliente: 403 Forbidden
    end
    API->>DB: COUNT contas com status "ativo" do cliente
    DB-->>API: Total de contas ativas
    alt Total >= 3
        API-->>Cliente: 422 Unprocessable Entity (Limite atingido)
    else Total < 3
        API->>DB: INSERT Account (balance=0)
        API-->>Cliente: 201 Created
    end
```

**2. Fluxo de Consulta de Extrato (Paginação e Segurança)**
A rota de extrato não requer isolamento transacional (*lock* de banco) pois trata-se de uma leitura idempotente, focada em segurança de acesso:

1. **Recepção:** O cliente solicita `GET /accounts/{key}/statement?limit=10&page=1`.
2. **Autorização JWT:** A API extrai o dono da requisição do JWT. Caso a conta alvo `{key}` não pertença ao cliente autenticado, a API barra imediatamente com `403`.
3. **Consulta de Histórico:** O sistema busca no banco transações onde a conta seja `origin_account_id` **OU** `destination_account_id`.
4. **Paginação:** Aplica-se ordenação decrescente por data (`created_at`). Baseado no `limit` e no *offset* (calculado via `page`), o sistema formata o retorno.
5. **Retorno:** O cliente recebe `200 OK` com o histórico e a consistência das flags de navegação (como `is_last_page`).

**3. Fluxo Lógico de Depósito**
Diferente da transferência, o depósito é uma operação unilateral (sem conta de origem) e o único momento onde fundos são inseridos organicamente no sistema.

* **Caminho Feliz:**
  1. A API recebe `POST /transactions` com `type: deposit`, o valor (`amount > 0`) e a conta alvo.
  2. Verifica-se o status da conta. Sendo `active`, a transação de banco é iniciada.
  3. O PostgreSQL soma o saldo e registra a linha na tabela `Transaction` (com `origin_account_id` como Nulo). 
  4. Ocorre o Commit e o cliente recebe 201.
* **Caminho de Falha (Conta Inválida/Bloqueada):**
  1. O payload é aceito pelo Schema, mas o código avalia que o status da conta no SGBD é `blocked` ou `closed`.
  2. Nenhum `UPDATE` de saldo ou `INSERT` de histórico é gerado.
  3. A API aborta o fluxo e retorna `422 Unprocessable Entity` informando o status inválido da conta.

**4. Fluxo de Transferências e Tarifas**
> 🚧 **[EM ABERTO - DEPENDE DA IMPLEMENTAÇÃO]**
> *Os fluxogramas exatos de transferência (incluindo cálculo dinâmico e roteamento das tarifas de TED/PIX) estão pausados. Eles serão detalhados aqui após validarmos a ordem de travamento dos saldos no código real.*

> ### Principal desafio
> * **Qual é:** Integridade transacional e *Race Conditions* (Condições de Corrida) no controle do saldo bancário.
> * **Por que é difícil:** Se ocorrerem 20 transferências simultâneas de R$ 100 em uma conta que tem apenas R$ 1.000, o ORM na camada de aplicação (Python) tende a ler o saldo "R$ 1.000" para todas as 20 requisições simultaneamente, antes que qualquer abatimento de fato termine. Com isso, o sistema aprova as transações baseado num "saldo fantasma", concluindo todas elas e negativando a conta (criando dinheiro irreal) sem acionar o validador.
> * **Como o desenho resolve:** Através do isolamento transacional utilizando **Pessimistic Locking**. A transação inicia um `SELECT ... FOR UPDATE` ordenando os IDs das contas envolvidas para evitar *deadlocks*. Esse mecanismo obriga o banco de dados (PostgreSQL) a formar uma "fila de espera": a segunda requisição concorrente só conseguirá ler o saldo e operar depois que a primeira descontar o valor e soltar a linha (dar o `COMMIT`). Isso barra gastos indevidos assim que o dinheiro real bate em zero.
