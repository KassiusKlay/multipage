import streamlit as st

st.title("👋 Introdução")

st.markdown(
    """
        Bemvindo ao meu site de projectos em Python 🐍\n
        Desde 2018 que comecei a interessar-me por programação (entre outras coisas),\
        pelo que quando o [Streamlit](https://www.streamlit.io) finalmente \
        lancou as apps multipáginas, \
        decidi agrupar e publicar os projectos que tenho desenvolvido \
        nas horas vagas.\n
        Eis uma breve descrição do que poderão encontrar:\n
        ---
    """
)

st.subheader(" 📉 [Stock Drop](/Stock_Drop)")

st.markdown(
    """
        Se investem em acções como eu, certamente já passaram por períodos de maior\
                volatilidade e aperto.\n
        Nesta app podem consultar a vossa empresa preferida e verificar quantas \
                quedas superiores a 10% já sofreu anteriormente.\n
        O passado não serve de exemplo para o futuro, mas trás algum descanso!\n
         *‘Be Fearful When Others Are Greedy and Greedy When \
                Others Are Fearful’* — Warren Buffett\n
        ---
     """
)

st.subheader("🍲 [Food](/Food)")

st.markdown(
    """
    Sou Vegan desde 2019 e um dos comentários que mais frequentemente oiço \
            é que as pessoas não seriam capazes porque a comida é sempre a mesma.\n
    Apesar do veganismo \
            [ser mais do que boa comida](https://www.youtube.com/watch?v=LQRAfJyEsko),\
    nesta app podem consultar todas as fotografias que tirei aos pratos que comi, \
    em casa 🏠 e pelo mundo 🌍.\n
    Deliciem-se!\n
    ---
    """
)

st.subheader("🏘️ [Remax](/Remax)")

st.markdown(
    """
    Procurar casas online às vezes é um sacrifício. É difícil filtrar o que \
            realmente nos interessa. \n
    Como a remax é a maior empresa imobiliária em Portugal, criei uma app \
            que replica o site com alguns dados adicionais, tais como:\n
      * Evolução da oferta no site
      * Tendências do mercado, com evolução do preço por metro quadrado
      * Mapa a cores de acordo com o preço por metro quadrado
    O objectivo final é criar um algoritmo de recomendação personalizado baseado \
            nas fotos das casas, para receber alertas quando uma nova casa **bonita!**\
            é colocada no site.
    """
)
