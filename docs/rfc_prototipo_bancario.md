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

### Banco de Dados (Somente diagrama)
*(Nesta seção, crie o modelo completo de entidades. Foco no que garante unicidade e guarda o estado.)*

```mermaid
erDiagram
    CUSTOMER {
        uuid id PK
        string document_number UK
        string email UK
        string password_hash
        string status
    }
    ACCOUNT {
        uuid id PK
        uuid customer_id FK
        string number UK
        decimal balance
        string status
        string type
    }
    TRANSACTION {
        uuid id PK
        uuid origin_account_id FK
        uuid destination_account_id FK
        decimal amount
        string type
        datetime created_at
    }
    FEE {
        uuid id PK
        uuid transaction_id FK
        decimal fee_amount
    }

    CUSTOMER ||--o{ ACCOUNT : "possui"
    ACCOUNT ||--o{ TRANSACTION : "envia / recebe"
    TRANSACTION ||--o| FEE : "gera tarifa"
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
* **Conta (`ACCOUNT.status`):** Uma conta só pode enviar ou receber fundos se estiver **ativa**[cite: 2]. Contas com status **inativo, bloqueado ou encerrado** são rejeitadas imediatamente na camada de validação de negócios[cite: 2].
* **Transação (`TRANSACTION_STATUS`):** O ciclo de uma transação transita por estados padronizados. Toda transação nasce como **'pending'** e só avança para **'confirmed'** após o sucesso da execução atômica do banco de dados[cite: 2]. Falhas de saldo ou regras de negócio resultam em **'failed'** ou status de erro análogo.

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
| POST | `/customers` | Cria o cliente | `document_number`, `email`, `password` | 201 criado; 409 CPF/email já existe; 422 dados inválidos |
| POST | `/auth/login` | Autentica cliente | `document_number`, `password` | 200 retorna JWT; 401 senha/hash inválidos |
| POST | `/customers/{key}/accounts` | Abre nova conta | `type` | 201 criada; 401 sem JWT; 422 > 3 contas ativas |
| GET | `/accounts` | Lista contas (idempotente) | JWT do Header | 200 listagem do cliente logado |
| POST | `/transactions` | Faz transferência | `type`, `amount`, `destination_account_key` | 201 transferido; 403 origem de outro; 422 sem saldo |
| GET | `/accounts/{key}/statement` | Extrato (idempotente)| `limit`, `page` | 200 devolve paginado; 400 período invertido |

#### Fluxos

**Transação de Transferência — Caminho Feliz**
```mermaid
sequenceDiagram
    actor Cliente
    participant API as FastAPI
    participant DB as PostgreSQL
    
    Cliente->>API: POST /transactions (amount, destino)
    API->>API: Valida JWT e dono da origem
    API->>DB: Inicia Transação
    API->>DB: SELECT FOR UPDATE (origem e destino)
    DB-->>API: Saldos travados
    API->>API: Calcula Tarifas e abate Saldo Origem
    API->>API: Soma Saldo Destino
    API->>DB: UPDATE Saldos + INSERT Transaction
    API->>DB: COMMIT (Libera travas)
    API-->>Cliente: 201 Created
```

**Transação de Transferência — Falha: Saldo Insuficiente**
1. O Cliente faz o request e o JWT é validado.
2. A transação inicia e as linhas são travadas no Banco de Dados.
3. O sistema calcula a tarifa da transferência e avalia: `Saldo Origem < (Valor + Tarifa)`.
4. Ocorre um `ROLLBACK` no banco, cancelando e soltando todas as travas imediatamente.
5. A API retorna `422 Unprocessable Entity` para o cliente.

> ### Principal desafio
> * **Qual é:** Concorrência no controle de saldo.
> * **Por que é difícil:** Requisições simultâneas lendo o mesmo saldo ao mesmo tempo geram estado fantasma, permitindo aprovar múltiplas transferências com dinheiro que não existe.
> * **Como o desenho resolve:** Através do isolamento transacional com *Pessimistic Locking* no Banco de Dados (`SELECT ... FOR UPDATE`), enfileirando requisições concorrentes diretamente no SGBD antes de ler o saldo real.
