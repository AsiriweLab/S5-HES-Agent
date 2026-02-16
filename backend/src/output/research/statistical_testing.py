"""
Statistical Testing Tools

Provides statistical analysis tools for research experiments,
including hypothesis testing, effect sizes, and confidence intervals.
"""

import math
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class TestType(str, Enum):
    """Type of statistical test."""
    T_TEST_INDEPENDENT = "t_test_independent"
    T_TEST_PAIRED = "t_test_paired"
    ANOVA_ONE_WAY = "anova_one_way"
    MANN_WHITNEY_U = "mann_whitney_u"
    WILCOXON_SIGNED_RANK = "wilcoxon_signed_rank"
    KRUSKAL_WALLIS = "kruskal_wallis"
    CHI_SQUARE = "chi_square"
    CORRELATION_PEARSON = "correlation_pearson"
    CORRELATION_SPEARMAN = "correlation_spearman"


class EffectSizeType(str, Enum):
    """Type of effect size calculation."""
    COHENS_D = "cohens_d"
    HEDGES_G = "hedges_g"
    GLASS_DELTA = "glass_delta"
    ETA_SQUARED = "eta_squared"
    OMEGA_SQUARED = "omega_squared"
    CRAMERS_V = "cramers_v"
    CORRELATION_R = "correlation_r"


class SignificanceLevel(str, Enum):
    """Common significance levels."""
    ALPHA_01 = "0.01"
    ALPHA_05 = "0.05"
    ALPHA_10 = "0.10"


class TestResult(BaseModel):
    """Result of a statistical test."""
    test_type: TestType
    test_statistic: float
    p_value: float
    degrees_of_freedom: Optional[float] = None
    effect_size: Optional[float] = None
    effect_size_type: Optional[EffectSizeType] = None
    confidence_interval: Optional[tuple[float, float]] = None
    confidence_level: float = 0.95
    is_significant: bool = False
    alpha: float = 0.05
    interpretation: str = ""
    sample_sizes: list[int] = Field(default_factory=list)
    group_means: list[float] = Field(default_factory=list)
    group_stds: list[float] = Field(default_factory=list)


class DescriptiveStats(BaseModel):
    """Descriptive statistics for a sample."""
    n: int
    mean: float
    median: float
    std_dev: float
    variance: float
    std_error: float
    min_val: float
    max_val: float
    range_val: float
    q1: float
    q3: float
    iqr: float
    skewness: Optional[float] = None
    kurtosis: Optional[float] = None


class MultipleComparisonResult(BaseModel):
    """Result of multiple comparison correction."""
    original_p_values: list[float]
    corrected_p_values: list[float]
    correction_method: str
    significant_indices: list[int]
    alpha: float = 0.05


class PowerAnalysisResult(BaseModel):
    """Result of power analysis."""
    effect_size: float
    alpha: float
    power: float
    sample_size_per_group: int
    total_sample_size: int


@dataclass
class StatisticalTestingTools:
    """
    Statistical testing tools for research analysis.

    Supports:
    - Parametric tests (t-test, ANOVA)
    - Non-parametric tests (Mann-Whitney, Kruskal-Wallis)
    - Effect size calculations
    - Confidence intervals
    - Multiple comparison corrections
    """

    default_alpha: float = 0.05
    default_confidence: float = 0.95

    def descriptive_statistics(self, data: list[float]) -> DescriptiveStats:
        """Calculate descriptive statistics for a sample."""
        import statistics

        n = len(data)
        if n == 0:
            raise ValueError("Data cannot be empty")

        sorted_data = sorted(data)
        mean = statistics.mean(data)
        median = statistics.median(data)
        std_dev = statistics.stdev(data) if n > 1 else 0
        variance = statistics.variance(data) if n > 1 else 0

        # Quartiles
        q1_idx = n // 4
        q3_idx = (3 * n) // 4
        q1 = sorted_data[q1_idx] if n >= 4 else sorted_data[0]
        q3 = sorted_data[q3_idx] if n >= 4 else sorted_data[-1]

        return DescriptiveStats(
            n=n,
            mean=mean,
            median=median,
            std_dev=std_dev,
            variance=variance,
            std_error=std_dev / math.sqrt(n) if n > 0 else 0,
            min_val=min(data),
            max_val=max(data),
            range_val=max(data) - min(data),
            q1=q1,
            q3=q3,
            iqr=q3 - q1,
        )

    def t_test_independent(
        self,
        group1: list[float],
        group2: list[float],
        alpha: Optional[float] = None,
        equal_variance: bool = True,
    ) -> TestResult:
        """
        Perform independent samples t-test.

        Args:
            group1: First sample data
            group2: Second sample data
            alpha: Significance level (default: 0.05)
            equal_variance: Assume equal variances (default: True)

        Returns:
            TestResult with t-statistic, p-value, and effect size
        """
        from scipy import stats

        alpha = alpha or self.default_alpha

        # Perform t-test
        if equal_variance:
            t_stat, p_value = stats.ttest_ind(group1, group2)
        else:
            t_stat, p_value = stats.ttest_ind(group1, group2, equal_var=False)

        # Calculate degrees of freedom
        n1, n2 = len(group1), len(group2)
        df = n1 + n2 - 2 if equal_variance else self._welch_df(group1, group2)

        # Calculate effect size (Cohen's d)
        effect_size = self.cohens_d(group1, group2)

        # Calculate confidence interval for difference in means
        mean_diff = sum(group1) / n1 - sum(group2) / n2
        pooled_se = self._pooled_standard_error(group1, group2)
        t_crit = stats.t.ppf(1 - alpha / 2, df)
        ci = (mean_diff - t_crit * pooled_se, mean_diff + t_crit * pooled_se)

        # Interpretation
        is_significant = p_value < alpha
        interpretation = self._interpret_t_test(p_value, effect_size, alpha)

        return TestResult(
            test_type=TestType.T_TEST_INDEPENDENT,
            test_statistic=float(t_stat),
            p_value=float(p_value),
            degrees_of_freedom=df,
            effect_size=effect_size,
            effect_size_type=EffectSizeType.COHENS_D,
            confidence_interval=ci,
            confidence_level=1 - alpha,
            is_significant=is_significant,
            alpha=alpha,
            interpretation=interpretation,
            sample_sizes=[n1, n2],
            group_means=[sum(group1) / n1, sum(group2) / n2],
            group_stds=[self._std_dev(group1), self._std_dev(group2)],
        )

    def t_test_paired(
        self,
        before: list[float],
        after: list[float],
        alpha: Optional[float] = None,
    ) -> TestResult:
        """Perform paired samples t-test."""
        from scipy import stats

        if len(before) != len(after):
            raise ValueError("Samples must have the same length for paired t-test")

        alpha = alpha or self.default_alpha

        t_stat, p_value = stats.ttest_rel(before, after)
        n = len(before)
        df = n - 1

        # Effect size for paired samples
        differences = [a - b for a, b in zip(after, before)]
        mean_diff = sum(differences) / n
        std_diff = self._std_dev(differences)
        effect_size = mean_diff / std_diff if std_diff > 0 else 0

        is_significant = p_value < alpha

        return TestResult(
            test_type=TestType.T_TEST_PAIRED,
            test_statistic=float(t_stat),
            p_value=float(p_value),
            degrees_of_freedom=df,
            effect_size=effect_size,
            effect_size_type=EffectSizeType.COHENS_D,
            is_significant=is_significant,
            alpha=alpha,
            interpretation=self._interpret_t_test(p_value, effect_size, alpha),
            sample_sizes=[n],
            group_means=[sum(before) / n, sum(after) / n],
        )

    def anova_one_way(
        self,
        *groups: list[float],
        alpha: Optional[float] = None,
    ) -> TestResult:
        """
        Perform one-way ANOVA.

        Args:
            *groups: Two or more groups of data
            alpha: Significance level

        Returns:
            TestResult with F-statistic, p-value, and eta-squared effect size
        """
        from scipy import stats

        if len(groups) < 2:
            raise ValueError("ANOVA requires at least 2 groups")

        alpha = alpha or self.default_alpha

        f_stat, p_value = stats.f_oneway(*groups)

        # Calculate degrees of freedom
        k = len(groups)  # number of groups
        n_total = sum(len(g) for g in groups)
        df_between = k - 1
        df_within = n_total - k

        # Calculate eta-squared
        effect_size = self.eta_squared(list(groups))

        is_significant = p_value < alpha
        interpretation = self._interpret_anova(p_value, effect_size, alpha, k)

        return TestResult(
            test_type=TestType.ANOVA_ONE_WAY,
            test_statistic=float(f_stat),
            p_value=float(p_value),
            degrees_of_freedom=df_between,
            effect_size=effect_size,
            effect_size_type=EffectSizeType.ETA_SQUARED,
            is_significant=is_significant,
            alpha=alpha,
            interpretation=interpretation,
            sample_sizes=[len(g) for g in groups],
            group_means=[sum(g) / len(g) for g in groups],
            group_stds=[self._std_dev(g) for g in groups],
        )

    def mann_whitney_u(
        self,
        group1: list[float],
        group2: list[float],
        alpha: Optional[float] = None,
    ) -> TestResult:
        """
        Perform Mann-Whitney U test (non-parametric alternative to t-test).
        """
        from scipy import stats

        alpha = alpha or self.default_alpha

        u_stat, p_value = stats.mannwhitneyu(group1, group2, alternative='two-sided')

        n1, n2 = len(group1), len(group2)

        # Calculate effect size (r = Z / sqrt(N))
        z_score = stats.norm.ppf(1 - p_value / 2)
        effect_size = z_score / math.sqrt(n1 + n2)

        is_significant = p_value < alpha

        return TestResult(
            test_type=TestType.MANN_WHITNEY_U,
            test_statistic=float(u_stat),
            p_value=float(p_value),
            effect_size=abs(effect_size),
            effect_size_type=EffectSizeType.CORRELATION_R,
            is_significant=is_significant,
            alpha=alpha,
            interpretation=self._interpret_nonparametric(p_value, effect_size, alpha),
            sample_sizes=[n1, n2],
            group_means=[sum(group1) / n1, sum(group2) / n2],
        )

    def kruskal_wallis(
        self,
        *groups: list[float],
        alpha: Optional[float] = None,
    ) -> TestResult:
        """
        Perform Kruskal-Wallis H test (non-parametric alternative to ANOVA).
        """
        from scipy import stats

        if len(groups) < 2:
            raise ValueError("Kruskal-Wallis requires at least 2 groups")

        alpha = alpha or self.default_alpha

        h_stat, p_value = stats.kruskal(*groups)

        # Calculate effect size (epsilon-squared)
        n_total = sum(len(g) for g in groups)
        effect_size = (h_stat - len(groups) + 1) / (n_total - len(groups))
        effect_size = max(0, min(1, effect_size))  # Bound between 0 and 1

        is_significant = p_value < alpha

        return TestResult(
            test_type=TestType.KRUSKAL_WALLIS,
            test_statistic=float(h_stat),
            p_value=float(p_value),
            effect_size=effect_size,
            is_significant=is_significant,
            alpha=alpha,
            interpretation=self._interpret_nonparametric(p_value, effect_size, alpha),
            sample_sizes=[len(g) for g in groups],
            group_means=[sum(g) / len(g) for g in groups],
        )

    def correlation_pearson(
        self,
        x: list[float],
        y: list[float],
        alpha: Optional[float] = None,
    ) -> TestResult:
        """Calculate Pearson correlation coefficient."""
        from scipy import stats

        if len(x) != len(y):
            raise ValueError("x and y must have the same length")

        alpha = alpha or self.default_alpha

        r, p_value = stats.pearsonr(x, y)
        n = len(x)

        # Calculate confidence interval for r
        z = 0.5 * math.log((1 + r) / (1 - r)) if abs(r) < 1 else 0
        se = 1 / math.sqrt(n - 3) if n > 3 else 0
        z_crit = stats.norm.ppf(1 - alpha / 2)
        z_lower, z_upper = z - z_crit * se, z + z_crit * se
        r_lower = (math.exp(2 * z_lower) - 1) / (math.exp(2 * z_lower) + 1)
        r_upper = (math.exp(2 * z_upper) - 1) / (math.exp(2 * z_upper) + 1)

        is_significant = p_value < alpha

        return TestResult(
            test_type=TestType.CORRELATION_PEARSON,
            test_statistic=float(r),
            p_value=float(p_value),
            degrees_of_freedom=n - 2,
            effect_size=abs(r),
            effect_size_type=EffectSizeType.CORRELATION_R,
            confidence_interval=(r_lower, r_upper),
            is_significant=is_significant,
            alpha=alpha,
            interpretation=self._interpret_correlation(r, p_value, alpha),
            sample_sizes=[n],
        )

    def correlation_spearman(
        self,
        x: list[float],
        y: list[float],
        alpha: Optional[float] = None,
    ) -> TestResult:
        """Calculate Spearman rank correlation coefficient."""
        from scipy import stats

        if len(x) != len(y):
            raise ValueError("x and y must have the same length")

        alpha = alpha or self.default_alpha

        rho, p_value = stats.spearmanr(x, y)
        n = len(x)

        # Calculate confidence interval for rho using Fisher's z transformation
        z = 0.5 * math.log((1 + rho) / (1 - rho)) if abs(rho) < 1 else 0
        se = 1 / math.sqrt(n - 3) if n > 3 else 0
        z_crit = stats.norm.ppf(1 - alpha / 2)
        z_lower, z_upper = z - z_crit * se, z + z_crit * se
        rho_lower = (math.exp(2 * z_lower) - 1) / (math.exp(2 * z_lower) + 1)
        rho_upper = (math.exp(2 * z_upper) - 1) / (math.exp(2 * z_upper) + 1)

        is_significant = p_value < alpha

        return TestResult(
            test_type=TestType.CORRELATION_SPEARMAN,
            test_statistic=float(rho),
            p_value=float(p_value),
            degrees_of_freedom=n - 2,
            effect_size=abs(rho),
            effect_size_type=EffectSizeType.CORRELATION_R,
            confidence_interval=(rho_lower, rho_upper),
            is_significant=is_significant,
            alpha=alpha,
            interpretation=self._interpret_correlation(rho, p_value, alpha),
            sample_sizes=[n],
        )

    def cohens_d(self, group1: list[float], group2: list[float]) -> float:
        """Calculate Cohen's d effect size."""
        n1, n2 = len(group1), len(group2)
        mean1, mean2 = sum(group1) / n1, sum(group2) / n2
        var1 = sum((x - mean1) ** 2 for x in group1) / (n1 - 1) if n1 > 1 else 0
        var2 = sum((x - mean2) ** 2 for x in group2) / (n2 - 1) if n2 > 1 else 0

        # Pooled standard deviation
        pooled_var = ((n1 - 1) * var1 + (n2 - 1) * var2) / (n1 + n2 - 2)
        pooled_std = math.sqrt(pooled_var) if pooled_var > 0 else 1

        return (mean1 - mean2) / pooled_std

    def hedges_g(self, group1: list[float], group2: list[float]) -> float:
        """Calculate Hedges' g effect size (bias-corrected Cohen's d)."""
        d = self.cohens_d(group1, group2)
        n = len(group1) + len(group2)
        correction = 1 - (3 / (4 * (n - 2) - 1))
        return d * correction

    def eta_squared(self, groups: list[list[float]]) -> float:
        """Calculate eta-squared effect size for ANOVA."""
        all_values = [x for g in groups for x in g]
        grand_mean = sum(all_values) / len(all_values)

        # Total sum of squares
        ss_total = sum((x - grand_mean) ** 2 for x in all_values)

        # Between-group sum of squares
        ss_between = sum(
            len(g) * (sum(g) / len(g) - grand_mean) ** 2
            for g in groups
        )

        return ss_between / ss_total if ss_total > 0 else 0

    def confidence_interval_mean(
        self,
        data: list[float],
        confidence: Optional[float] = None,
    ) -> tuple[float, float]:
        """Calculate confidence interval for the mean."""
        from scipy import stats

        confidence = confidence or self.default_confidence
        n = len(data)
        mean = sum(data) / n
        std_err = self._std_dev(data) / math.sqrt(n)

        t_crit = stats.t.ppf((1 + confidence) / 2, n - 1)
        margin = t_crit * std_err

        return (mean - margin, mean + margin)

    def bonferroni_correction(
        self,
        p_values: list[float],
        alpha: Optional[float] = None,
    ) -> MultipleComparisonResult:
        """Apply Bonferroni correction for multiple comparisons."""
        alpha = alpha or self.default_alpha
        k = len(p_values)
        corrected = [min(p * k, 1.0) for p in p_values]
        significant = [i for i, p in enumerate(corrected) if p < alpha]

        return MultipleComparisonResult(
            original_p_values=p_values,
            corrected_p_values=corrected,
            correction_method="bonferroni",
            significant_indices=significant,
            alpha=alpha,
        )

    def holm_correction(
        self,
        p_values: list[float],
        alpha: Optional[float] = None,
    ) -> MultipleComparisonResult:
        """Apply Holm-Bonferroni correction (less conservative than Bonferroni)."""
        alpha = alpha or self.default_alpha
        k = len(p_values)

        # Sort p-values and track original indices
        indexed = sorted(enumerate(p_values), key=lambda x: x[1])
        corrected = [0.0] * k

        for rank, (orig_idx, p) in enumerate(indexed):
            corrected[orig_idx] = min(p * (k - rank), 1.0)

        # Ensure monotonicity
        for i in range(1, k):
            idx = indexed[i][0]
            prev_idx = indexed[i - 1][0]
            corrected[idx] = max(corrected[idx], corrected[prev_idx])

        significant = [i for i, p in enumerate(corrected) if p < alpha]

        return MultipleComparisonResult(
            original_p_values=p_values,
            corrected_p_values=corrected,
            correction_method="holm",
            significant_indices=significant,
            alpha=alpha,
        )

    def fdr_correction(
        self,
        p_values: list[float],
        alpha: Optional[float] = None,
    ) -> MultipleComparisonResult:
        """Apply Benjamini-Hochberg FDR correction."""
        alpha = alpha or self.default_alpha
        k = len(p_values)

        # Sort p-values and track original indices
        indexed = sorted(enumerate(p_values), key=lambda x: x[1])
        corrected = [0.0] * k

        for rank, (orig_idx, p) in enumerate(indexed, 1):
            corrected[orig_idx] = min(p * k / rank, 1.0)

        # Ensure monotonicity (from largest to smallest)
        for i in range(k - 2, -1, -1):
            idx = indexed[i][0]
            next_idx = indexed[i + 1][0]
            corrected[idx] = min(corrected[idx], corrected[next_idx])

        significant = [i for i, p in enumerate(corrected) if p < alpha]

        return MultipleComparisonResult(
            original_p_values=p_values,
            corrected_p_values=corrected,
            correction_method="fdr_bh",
            significant_indices=significant,
            alpha=alpha,
        )

    def power_analysis_t_test(
        self,
        effect_size: float,
        alpha: float = 0.05,
        power: float = 0.80,
    ) -> PowerAnalysisResult:
        """
        Calculate required sample size for t-test.

        Args:
            effect_size: Expected Cohen's d effect size
            alpha: Significance level
            power: Desired statistical power

        Returns:
            PowerAnalysisResult with required sample sizes
        """
        from scipy import stats

        # Use approximation formula for two-sample t-test
        z_alpha = stats.norm.ppf(1 - alpha / 2)
        z_beta = stats.norm.ppf(power)

        # Sample size per group
        n = 2 * ((z_alpha + z_beta) / effect_size) ** 2
        n_per_group = math.ceil(n)

        return PowerAnalysisResult(
            effect_size=effect_size,
            alpha=alpha,
            power=power,
            sample_size_per_group=n_per_group,
            total_sample_size=n_per_group * 2,
        )

    # Helper methods
    def _std_dev(self, data: list[float]) -> float:
        """Calculate sample standard deviation."""
        n = len(data)
        if n < 2:
            return 0
        mean = sum(data) / n
        return math.sqrt(sum((x - mean) ** 2 for x in data) / (n - 1))

    def _pooled_standard_error(self, group1: list[float], group2: list[float]) -> float:
        """Calculate pooled standard error for two samples."""
        n1, n2 = len(group1), len(group2)
        var1 = sum((x - sum(group1) / n1) ** 2 for x in group1) / (n1 - 1) if n1 > 1 else 0
        var2 = sum((x - sum(group2) / n2) ** 2 for x in group2) / (n2 - 1) if n2 > 1 else 0
        return math.sqrt(var1 / n1 + var2 / n2)

    def _welch_df(self, group1: list[float], group2: list[float]) -> float:
        """Calculate Welch's degrees of freedom."""
        n1, n2 = len(group1), len(group2)
        var1 = sum((x - sum(group1) / n1) ** 2 for x in group1) / (n1 - 1) if n1 > 1 else 0
        var2 = sum((x - sum(group2) / n2) ** 2 for x in group2) / (n2 - 1) if n2 > 1 else 0

        num = (var1 / n1 + var2 / n2) ** 2
        denom = (var1 / n1) ** 2 / (n1 - 1) + (var2 / n2) ** 2 / (n2 - 1)
        return num / denom if denom > 0 else n1 + n2 - 2

    def _interpret_t_test(self, p_value: float, effect_size: float, alpha: float) -> str:
        """Generate interpretation for t-test results."""
        sig_text = "statistically significant" if p_value < alpha else "not statistically significant"
        effect_text = self._effect_size_interpretation(abs(effect_size))
        return f"The difference is {sig_text} (p = {p_value:.4f}). The effect size is {effect_text} (d = {effect_size:.3f})."

    def _interpret_anova(self, p_value: float, effect_size: float, alpha: float, k: int) -> str:
        """Generate interpretation for ANOVA results."""
        sig_text = "statistically significant" if p_value < alpha else "not statistically significant"
        effect_text = self._effect_size_interpretation_eta(effect_size)
        return f"The difference between {k} groups is {sig_text} (p = {p_value:.4f}). The effect size is {effect_text} (η² = {effect_size:.3f})."

    def _interpret_nonparametric(self, p_value: float, effect_size: float, alpha: float) -> str:
        """Generate interpretation for non-parametric test results."""
        sig_text = "statistically significant" if p_value < alpha else "not statistically significant"
        return f"The difference is {sig_text} (p = {p_value:.4f}, effect size r = {abs(effect_size):.3f})."

    def _interpret_correlation(self, r: float, p_value: float, alpha: float) -> str:
        """Generate interpretation for correlation results."""
        sig_text = "statistically significant" if p_value < alpha else "not statistically significant"
        strength = self._correlation_strength(abs(r))
        direction = "positive" if r > 0 else "negative"
        return f"There is a {sig_text} {strength} {direction} correlation (r = {r:.3f}, p = {p_value:.4f})."

    def _effect_size_interpretation(self, d: float) -> str:
        """Interpret Cohen's d effect size."""
        if d < 0.2:
            return "negligible"
        elif d < 0.5:
            return "small"
        elif d < 0.8:
            return "medium"
        else:
            return "large"

    def _effect_size_interpretation_eta(self, eta_sq: float) -> str:
        """Interpret eta-squared effect size."""
        if eta_sq < 0.01:
            return "negligible"
        elif eta_sq < 0.06:
            return "small"
        elif eta_sq < 0.14:
            return "medium"
        else:
            return "large"

    def _correlation_strength(self, r: float) -> str:
        """Interpret correlation strength."""
        if r < 0.1:
            return "negligible"
        elif r < 0.3:
            return "weak"
        elif r < 0.5:
            return "moderate"
        elif r < 0.7:
            return "strong"
        else:
            return "very strong"


# Singleton instance
_stats_tools: Optional[StatisticalTestingTools] = None


def get_statistical_testing_tools() -> StatisticalTestingTools:
    """Get the global statistical testing tools instance."""
    global _stats_tools
    if _stats_tools is None:
        _stats_tools = StatisticalTestingTools()
    return _stats_tools