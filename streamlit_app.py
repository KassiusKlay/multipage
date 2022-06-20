import streamlit as st

st.title("Introdução")

st.markdown(
    """
        Bemvindo ao meu site.\n
        Chamo-me João Cassis, tenho x anos e actualmente trabalho como Medico\
                Patologista no Hospital da Luz em Lisboa.\n
        Desde 2018 que comecei a interessar-me por programacao (entre outras coisas),\
        pelo que quando o Streamlit finalmente lancou as apps multipaginas, \
        decidi agrupar e publicar os projectos que tenho desenvolvido \
        nas horas vagas.\n
        Eis uma breve descricao do que poderao encontrar:
    """
)

st.subheader("Stock Drop")

st.markdown(
    """
        Se investem em accoes como eu, certamente ja passaram por periodos de maior\
                volatilidade e apertos.\n
        Esta app serve para relembrar que rara e a empresa que nao sofra quedas \
                acentuadas, para depois muitas vezes recuperar e ultrapassar \
                maximos historicos.\n
        Basta procurar por Ticker e a app demonstra evolucao temporal do valor \
                das accoes, com evidencia nos periodos de maior queda \
                (superiores a 10%).
    """
)

st.subheader("Tesla Sentiment")

st.markdown(
    """
    Sempre me questionei se as noticias sobre uma empresa teriam impacto no valor \
            das suas accoes.\n
    Inttuitivamente pensariamos que sim, mas decidi por a prova.\n
    Corri um algoritmo de inteligencia artificial sobre todas as noticias da Tesla\
            do site dedicado a empresa Teslarati. \n
    Este algoritmo pontua as noticias \
            em positivas, negativas ou neutras, sendo que eu atribui um peso 4x \
            maior as noticias negativas vs positivas. \n
    Ate agora, o resultado nao me permite tirar grandes conclusoes, mas ainda estou a\
            terminar de registar as noticias mais antigas.
    """
)

st.subheader("Food")

st.markdown(
    """
    Sou Vegan desde 2019 e um dos comentarios que mais frequentemente oico \
            e que as pessoas nao seriam capazes porque a comida e sempre a mesma.\n
    Apesar do veganismo ser mais do que boa comida, decidi criar uma app que \
            demonstra todas as fotografias que tirei aos pratos que comi, em casa \
            e pelo mundo.
    Deliciem-se!
    """
)

st.subheader("Remax")

st.markdown(
    """
    Procurar casas online e um martirio.\n
    Como a remax e a maior empresa imobiliaria em Portugal, criei uma app que \
            que replica o site com alguns pontos adicionais, tais como:
            - evolucao da oferta no site
            - mapa a cores com as casas mais baratas por metro quadrado
            - evolucao temporal do preco por metro quadrado
    Em curso, um sistema de recomendacao de casas a partir de um algoritmo \
            de inteligencia artificial treinado por mim.\n
    """
)
