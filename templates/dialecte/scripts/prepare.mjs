/**
 * Runs on every `npm install` of this package (npm's `prepare`, after husky): writes the skill's API index from
 * the source, and the type-bench baseline of the scaffolded version (`__version__`) once, when there is none -
 * from then on the baseline is yours and changes only when you run `npm run type-bench`. A step that fails says
 * in one line how to run it by hand and lets the install finish: `npm run skills:check` and `dialecte contrib`
 * still report what is missing.
 */
import { spawnSync } from 'node:child_process'
import { existsSync } from 'node:fs'

function succeeds(params) {
	return spawnSync(params.command, { shell: true, stdio: 'ignore' }).status === 0
}

function writeSkillsIndex() {
	if (succeeds({ command: 'dialecte skills generate' })) return
	console.warn('skills index not generated: run `npm run skills:generate`')
}

function writeFirstTypeBenchBaseline() {
	if (existsSync('benchmarks/types/__version__/baseline.json')) return
	console.log(
		'writing the first type-bench baseline (benchmarks/types/__version__/baseline.json)...',
	)
	if (succeeds({ command: 'npm run type-bench' })) return
	console.warn('type-bench baseline not written: run `npm run type-bench`')
}

writeSkillsIndex()
writeFirstTypeBenchBaseline()
