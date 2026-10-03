CPF_LENGTH = 11

CHECK_DIGIT_POSITIONS = [9, 10]


def is_valid_cpf(document_number: str) -> bool:
    """Diz se um CPF existe de verdade — não se ele tem a cara certa.

    O schema em src/schemas/post_sample_entity.json já cobrou o formato:
    três pontos, um hífen, onze dígitos. Isto aqui é outra pergunta, e a
    diferença entre as duas é a lição deste arquivo.

    Os dois últimos dígitos de um CPF não são escolhidos: eles são o
    RESULTADO de uma conta feita sobre os nove primeiros. Por isso um
    número pode ter o formato perfeito e não existir — "111.222.333-44"
    passa no schema e não passa aqui.

    É o mesmo motivo pelo qual a resposta dessa recusa é 422 e não 400:
    não é que a API não conseguiu ler o pedido; ela leu, entendeu, e o
    valor não pode existir.

    A conta, para cada um dos dois dígitos: multiplica cada dígito
    anterior por um peso que decresce, soma tudo, tira o resto da divisão
    por 11. Resto menor que 2 vira dígito 0; nos outros casos, o dígito é
    11 menos o resto.
    """
    digits = []
    for character in document_number:
        if character.isdigit():
            digits.append(int(character))

    if len(digits) != CPF_LENGTH:
        return False

    # Um CPF de dígitos todos iguais ("111.111.111-11") passa na conta
    # dos dígitos verificadores e mesmo assim não vale. São onze números
    # conhecidos, e a Receita não emite nenhum deles.
    all_digits_are_equal = True
    for digit in digits:
        if digit != digits[0]:
            all_digits_are_equal = False
            break

    if all_digits_are_equal:
        return False

    for position in CHECK_DIGIT_POSITIONS:
        total = 0
        first_weight = position + 1

        for index in range(position):
            total = total + digits[index] * (first_weight - index)

        remainder = total % 11

        if remainder < 2:
            expected_digit = 0
        else:
            expected_digit = 11 - remainder

        if digits[position] != expected_digit:
            return False

    return True

CNPJ_LENGTH = 14

def is_valid_cnpj(document_number: str) -> bool:
    """Valida um CNPJ através dos seus dígitos verificadores."""
    digits = [int(c) for c in document_number if c.isdigit()]
    
    if len(digits) != CNPJ_LENGTH:
        return False
        
    if len(set(digits)) == 1:
        return False
        
    # Primeiro dígito
    weights_1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    total_1 = sum(d * w for d, w in zip(digits[:12], weights_1))
    remainder_1 = total_1 % 11
    expected_digit_1 = 0 if remainder_1 < 2 else 11 - remainder_1
    if digits[12] != expected_digit_1:
        return False
        
    # Segundo dígito
    weights_2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    total_2 = sum(d * w for d, w in zip(digits[:13], weights_2))
    remainder_2 = total_2 % 11
    expected_digit_2 = 0 if remainder_2 < 2 else 11 - remainder_2
    if digits[13] != expected_digit_2:
        return False
        
    return True
