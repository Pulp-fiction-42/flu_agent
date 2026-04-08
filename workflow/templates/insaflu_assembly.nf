/*
 * INSaFLU 标准流程 - 流感病毒组装与分析
 * Nextflow DSL2 模板
 *
 * 使用方法:
 *   nextflow run insaflu_assembly.nf \
 *     --reads "/data/*.fastq.gz" \
 *     --outdir "/data/output" \
 *     --segment "HA"
 *
 * 参数:
 *   --reads          输入 FastQ 文件路径 (支持通配符)
 *   --outdir         输出目录
 *   --segment        目标病毒片段 (HA, NA, PB1, PB2, PA, NP, M, NS)
 *   --reference      参考序列 (可选)
 *   --thread         线程数 (默认: 4)
 */
nextflow.enable.dsl = 2

// 参数验证
params.reads = "$params.outdir/reads/*.fastq.gz"
params.outdir = "$params.outdir"
params.segment = "HA"
params.reference = ""
params.thread = 4

// 日志输出
println "========================================="
println "INSaFLU 流感病毒分析流程"
println "========================================="
println "输入文件: ${params.reads}"
println "输出目录: ${params.outdir}"
println "目标片段: ${params.segment}"
println "线程数: ${params.thread}"
println "========================================="

// 引入预定义流程模块
include { IRMA_ASSEMBLY } from './modules/irma.nf'
include { VARIANT_CALLING } from './modules/variants.nf'
include { PHYLOGENY } from './modules/phylogeny.nf'

workflow {

    main:
        // Step 1: IRMA 组装
        IRMA_ASSEMBLY(params.reads, params.segment)

        // Step 2: 变异检测
        VARIANT_CALLING(
            IRMA_ASSEMBLY.out.assembly,
            params.reference
        )

        // Step 3: 进化分析
        PHYLOGENY(
            IRMA_ASSEMBLY.out.sequences
        )
}

workflow.onComplete {
    println "========================================="
    println "流程完成!"
    println "结果保存在: ${params.outdir}"
    println "========================================="
}