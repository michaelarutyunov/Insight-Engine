# Segmentation — Practitioner Workflow

## Pre-analysis checks
1. Verify feature variance — drop near-constant columns (variance < threshold)
2. Assess multicollinearity — consider dimensionality reduction if VIF > 5
3. Check for outliers — flag and decide handling strategy before clustering
4. Verify sample size adequacy — minimum ~50 observations per expected cluster
5. Confirm data types are compatible with chosen method (numeric for k-means, mixed for LCA)

## Method selection guidance within this family
- All numeric features, no strong priors → k-means clustering
- Mixed or categorical features → Latent Class Analysis (LCA)
- Transaction data with known value framework → RFM segmentation
- Need probabilistic cluster membership → LCA or Gaussian Mixture Models
- Small sample with many variables → Hierarchical clustering (Ward)

## Execution steps
6. Run with multiple k values (or equivalent parameter range)
7. Evaluate solutions using silhouette score + business interpretability
8. Profile segments on variables NOT used in clustering
9. Name segments using distinguishing profile characteristics
10. Validate stability by running on bootstrapped samples

## Reporting requirements
11. Report solution diagnostics alongside segment descriptions
12. Include segment sizes and stability indicators
13. Present results with and without outlier-sensitive observations
14. Document the final k selection rationale with supporting metrics
