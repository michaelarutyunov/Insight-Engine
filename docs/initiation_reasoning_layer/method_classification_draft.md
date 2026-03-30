| Method                                         | exploratory_confirmatory | assumption_weight | output_interpretability | sample_sensitivity | reproducibility | data_structure_affinity |
| ---------------------------------------------- | ------------------------ | ----------------- | ----------------------- | ------------------ | --------------- | ----------------------- |
| **K-means clustering**                         | exploratory              | medium            | medium                  | medium             | high            | numeric_continuous      |
| **Hierarchical clustering (Ward)**             | exploratory              | medium            | medium                  | low                | high            | numeric_continuous      |
| **Gaussian Mixture Models (GMM)**              | exploratory              | high              | medium                  | medium             | medium          | numeric_continuous      |
| **Latent Class Analysis (LCA)**                | mixed                    | high              | high                    | high               | medium          | categorical             |
| **DBSCAN**                                     | exploratory              | medium            | medium                  | low                | medium          | numeric_continuous      |
| **PCA**                                        | exploratory              | medium            | medium                  | medium             | high            | numeric_continuous      |
| **Exploratory Factor Analysis (EFA)**          | exploratory              | high              | medium                  | high               | medium          | numeric_continuous      |
| **Confirmatory Factor Analysis (CFA)**         | confirmatory             | high              | medium                  | high               | medium          | numeric_continuous      |
| **MDS**                                        | exploratory              | medium            | medium                  | medium             | medium          | mixed                   |
| **MCA**                                        | exploratory              | medium            | medium                  | medium             | high            | categorical             |
| **OLS regression (driver analysis)**           | confirmatory             | high              | high                    | medium             | high            | numeric_continuous      |
| **Logistic regression**                        | confirmatory             | high              | medium                  | medium             | high            | mixed                   |
| **Relative weights / Shapley drivers**         | mixed                    | medium            | high                    | medium             | medium          | mixed                   |
| **PLS regression (drivers)**                   | mixed                    | medium            | medium                  | medium             | medium          | numeric_continuous      |
| **SEM (Structural Equation Modelling)**        | confirmatory             | high              | medium                  | high               | medium          | mixed                   |
| **A/B testing**                                | confirmatory             | medium            | high                    | medium             | high            | mixed                   |
| **Conjoint (CBC)**                             | confirmatory             | high              | medium                  | high               | high            | mixed                   |
| **MaxDiff**                                    | mixed                    | medium            | high                    | medium             | high            | ordinal                 |
| **Discrete Choice Experiment (DCE)**           | confirmatory             | high              | medium                  | high               | medium          | mixed                   |
| **Marketing Mix Modelling (MMM)**              | confirmatory             | high              | medium                  | high               | medium          | numeric_continuous      |
| **Interrupted Time Series**                    | confirmatory             | high              | medium                  | high               | medium          | numeric_continuous      |
| **Thematic analysis**                          | exploratory              | low               | high                    | low                | low             | unstructured_text       |
| **Framework analysis**                         | mixed                    | medium            | high                    | low                | medium          | unstructured_text       |
| **Grounded theory coding**                     | exploratory              | low               | medium                  | low                | low             | unstructured_text       |
| **Ethnography / contextual inquiry**           | exploratory              | low               | high                    | low                | low             | mixed                   |
| **Diary study**                                | exploratory              | low               | high                    | low                | low             | mixed                   |
| **Manual content analysis**                    | mixed                    | medium            | high                    | low                | medium          | unstructured_text       |
| **Topic modelling (LDA)**                      | exploratory              | high              | low                     | medium             | high            | unstructured_text       |
| **Topic modelling (BERTopic / embeddings)**    | exploratory              | medium            | medium                  | low                | medium          | unstructured_text       |
| **Sentiment analysis (lexicon-based)**         | mixed                    | medium            | medium                  | low                | high            | unstructured_text       |
| **LLM-assisted coding (HITL)**                 | mixed                    | medium            | high                    | low                | medium          | unstructured_text       |
| **Synthetic respondents (persona simulation)** | exploratory              | high              | medium                  | low                | low             | mixed                   |
