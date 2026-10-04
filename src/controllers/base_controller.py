from abc import ABCMeta

from database import get_context
from utils.logger import get_logger
from utils.safe_log import format_fields


class BaseController(metaclass=ABCMeta):
    """O que todo controller tem em comum: a conexão com o banco e o log.

    Nada chega por parâmetro: o controller pega o CONTEXTO da requisição
    em que está rodando. Quem preparou esse contexto foi o middleware.

    Guardar o `self.context`, e não só a sessão, é o que permite o
    repository receber `context` em vez de `db`: o contexto é a coisa que
    viaja entre as camadas, e a sessão é só o que ele carrega hoje.

    É aqui que a sessão nasce, no `get_or_create_session` — construir um
    controller é a mesma coisa que dizer "eu uso banco".
    """

    def __init__(self, class_name: str) -> None:
        self.context = get_context()
        self.session = self.context.get_or_create_session()
        self.logger = get_logger(class_name)

    def _log_return(self, message: str, data=None, **events) -> None:
        """Escreve no log o que esta requisição devolveu — sem dado sensível.

        `data` é o que vai voltar (o DTO); passa por utils/safe_log.sanitize,
        que mascara CPF/CNPJ/e-mail, remove senha e esconde token. `events`
        descreve o que não pode ir no log, só o resultado:
        `senha="criada"`, `senha="conferida"`.

        Mesmo formato do middleware: a linha ganha sozinha o request_id.
        """
        fields = format_fields(data) if data is not None else ""
        extra = " ".join(f"{key}={value}" for key, value in events.items())
        details = " ".join(part for part in (fields, extra) if part)
        self.logger.info(f"RETORNO {message}" + (f" | {details}" if details else ""))
