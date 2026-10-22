# Single model of acceptance for the crossed design (reported in Section 3.4.1 of the paper, Table "glmm").
#
# GLMM logistico (glmmTMB, aproximacao de Laplace), intercepto aleatorio por questao;
# efeitos fixos: modelo, linguagem e dificuldade. Testes de razao de verossimilhanca (LRT)
# para cada fator (drop1) e para cada interacao de segunda ordem adicionada ao modelo principal.
#
# Uso (na raiz do repositorio): Rscript analysis/glmm.R [data/results.csv data/problems/sample.csv results/glmm]
# Requer R >= 4.1 e o pacote glmmTMB. Dados de entrada somente leitura.

suppressPackageStartupMessages({ library(glmmTMB) })
args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 3) {
  dd <- Sys.getenv("STUDY_DATA_DIR", "data"); rd <- Sys.getenv("STUDY_RESULTS_DIR", "results")
  args <- c(file.path(dd, "results.csv"), file.path(dd, "problems", "sample.csv"), file.path(rd, "glmm"))
}
arq_res <- args[1]; arq_sample <- args[2]; out <- args[3]
dir.create(out, showWarnings = FALSE, recursive = TRUE)

d <- read.csv(arq_res, stringsAsFactors = FALSE, encoding = "UTF-8")
s <- read.csv(arq_sample, stringsAsFactors = FALSE, encoding = "UTF-8")[, c("id", "dificuldade")]
names(s) <- c("id_questao", "dificuldade")
d$id_questao <- as.integer(round(as.numeric(d$id_questao)))
d <- merge(d, s, by = "id_questao", all.x = TRUE)
stopifnot(!any(is.na(d$dificuldade)))

# Facil / Media / Dificil (primeira letra evita problemas de acentuacao)
dif_map <- c(F = "Easy", M = "Medium", D = "Hard")
d$dif <- factor(dif_map[substr(d$dificuldade, 1, 1)], levels = c("Easy", "Medium", "Hard"))
stopifnot(!any(is.na(d$dif)))
d$acc <- as.integer(d$status == "Accepted")
d$linguagem <- factor(d$linguagem, levels = c("C++", "Java", "Python3"))
nome <- sub("^(meta-llama|moonshotai|qwen)_", "\\1/", d$modelo)
nome <- sub("^meta-llama/", "", nome)
d$modelo <- factor(nome)
ref <- if ("llama3-8b-8192" %in% levels(d$modelo)) "llama3-8b-8192" else levels(d$modelo)[1]  # referencia do artigo
d$modelo <- relevel(d$modelo, ref = ref)
d$q <- factor(d$id_questao)

fit <- function(f) {
  m <- glmmTMB(f, data = d, family = binomial)
  if (!isTRUE(m$sdr$pdHess)) warning("Hessiana nao positiva definida: ", deparse(f))
  m
}

m0 <- fit(acc ~ modelo + linguagem + dif + (1 | q))

# LRT de cada fator principal
lrt_fator <- function(termo) {
  m <- update(m0, as.formula(paste(". ~ . -", termo)))
  a <- anova(m, m0)
  c(chisq = a$Chisq[2], df = a$`Chi Df`[2], p = a$`Pr(>Chisq)`[2])
}
fatores <- sapply(c(modelo = "modelo", linguagem = "linguagem", dif = "dif"), lrt_fator)

# LRT de cada interacao de segunda ordem
lrt_int <- function(termo) {
  m <- update(m0, as.formula(paste(". ~ . +", termo)))
  a <- anova(m0, m)
  c(chisq = a$Chisq[2], df = a$`Chi Df`[2], p = a$`Pr(>Chisq)`[2],
    pdHess = as.numeric(isTRUE(m$sdr$pdHess)))
}
inter <- sapply(c("modelo:linguagem" = "modelo:linguagem", "modelo:dif" = "modelo:dif",
                  "linguagem:dif" = "linguagem:dif"), lrt_int)

# Odds ratios (Wald) do modelo principal
cf <- summary(m0)$coefficients$cond
or <- data.frame(termo = rownames(cf), OR = exp(cf[, 1]),
                 lo = exp(cf[, 1] - 1.96 * cf[, 2]), hi = exp(cf[, 1] + 1.96 * cf[, 2]),
                 p = cf[, 4], row.names = NULL)
sd_q <- attr(VarCorr(m0)$cond$q, "stddev")[[1]]
icc <- sd_q^2 / (sd_q^2 + pi^2 / 3)

write.csv(or, file.path(out, "glmm_or.csv"), row.names = FALSE)
write.csv(t(fatores), file.path(out, "glmm_lrt_fatores.csv"))
write.csv(t(inter), file.path(out, "glmm_lrt_interacoes.csv"))
writeLines(c(sprintf("n=%d questoes=%d aceitas=%d", nrow(d), nlevels(d$q), sum(d$acc)),
             sprintf("sd_questao=%.4f icc=%.4f", sd_q, icc),
             sprintf("pdHess_m0=%s convergence=%d", m0$sdr$pdHess, m0$fit$convergence),
             sprintf("glmmTMB=%s R=%s", packageVersion("glmmTMB"), R.version.string)),
           file.path(out, "glmm_resumo.txt"))
# Tabela LaTeX (apendice): OR condicionais com IC de Wald e LRT dos fatores/interacoes
fo <- function(x) if (x < 0.1) sprintf("%.3f", x) else sprintf("%.2f", x)
pf <- function(p) if (p < 0.001) "$<0.001$" else sprintf("$%.3f$", p)
lab <- function(t) {
  if (t == "(Intercept)") return(NA)
  if (startsWith(t, "modelo")) return(sprintf("\\texttt{%s}", sub("^modelo", "", t)))
  if (startsWith(t, "linguagem")) return(sprintf("Language: %s", sub("^linguagem", "", t)))
  sprintf("Difficulty: %s", sub("^dif", "", t))
}
o <- or[order(!startsWith(or$termo, "linguagem"), !startsWith(or$termo, "dif"), -or$OR), ]
tx <- c("\\begin{tabular}{lrr}", "\\hline\\hline",
        "\\textbf{Fixed effect} & \\textbf{OR [95\\% CI]} & \\textbf{$p$} \\\\", "\\hline")
for (i in seq_len(nrow(o))) { l <- lab(o$termo[i]); if (is.na(l)) next
  tx <- c(tx, sprintf("%s & %s [%s, %s] & %s \\\\", l, fo(o$OR[i]), fo(o$lo[i]), fo(o$hi[i]), pf(o$p[i]))) }
tx <- c(tx, "\\hline", "\\multicolumn{3}{l}{\\emph{Likelihood-ratio tests}} \\\\",
        "\\textbf{Term} & \\textbf{$\\chi^2$ (df)} & \\textbf{$p$} \\\\", "\\hline")
nm <- c(modelo = "Model", linguagem = "Language", dif = "Difficulty",
        "modelo:linguagem" = "Model $\\times$ Language", "modelo:dif" = "Model $\\times$ Difficulty",
        "linguagem:dif" = "Language $\\times$ Difficulty")
for (k in colnames(fatores)) tx <- c(tx, sprintf("%s & %.1f (%d) & %s \\\\", nm[k], fatores["chisq", k], fatores["df", k], pf(fatores["p", k])))
for (k in colnames(inter)) tx <- c(tx, sprintf("%s & %.1f (%d) & %s \\\\", nm[k], inter["chisq", k], inter["df", k], pf(inter["p", k])))
tx <- c(tx, "\\hline\\hline", "\\end{tabular}")
writeLines(tx, file.path(out, "tab_glmm.tex"))
print(fatores); print(inter); print(or, digits = 3); cat(readLines(file.path(out, "glmm_resumo.txt")), sep = "\n")
