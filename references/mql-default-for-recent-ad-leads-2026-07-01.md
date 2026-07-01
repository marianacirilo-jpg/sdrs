# Regra Rafael — leads recentes dos anúncios como MQL por padrão

Data: 2026-07-01

Rafael definiu que os leads que estão entrando agora pelos anúncios já vêm bem qualificados. Portanto, neste momento operacional:

1. Quando houver dúvida inicial / `pending_review`, considerar MQL.
2. Enviar para diagnóstico e sequência/follow-up; os follow-ups vão qualificar melhor a intenção.
3. Converter/marcar como MQL quando fizer sentido comercial mínimo e houver empresa/contato real.
4. Só desqualificar automaticamente quando for óbvio que é:
   - base teste / formulário admin / lead fake;
   - empresa sem nenhuma estrutura comercial real;
   - contato sem empresa/CNPJ/contexto mínimo;
   - totalmente fora de realidade ou claramente sem relação com operação comercial.
5. Casos como e-commerce pequeno, operação de serviço com produto físico, brindes, alimentos/temperos, dental/saúde com fluxo digital etc. NÃO devem cair automaticamente em Não-MQL apenas por dúvida de ICP; devem seguir diagnóstico para validar.

Implementado no intake rápido `scripts/active_mql_qualifier.py`: `pending_review` virou `mql_candidate_needs_main_pipeline` por padrão; `classified_non_mql_hint` fica reservado para teste/fake/sem empresa/sem estrutura clara.
