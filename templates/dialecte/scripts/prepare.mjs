/**
 * Runs on every `npm install` of this package (npm's `prepare`, after husky): writes the skill's API index from
 * the source. When it fails it says in one line how to run it by hand and lets the install finish:
 * `npm run skills:check` and `dialecte contrib` still report what is missing. The type bench stores nothing: it
 * measures each change against the base it goes onto.
 */
import { spawnSync } from 'node:child_process'

function succeeds(params) {
	return spawnSync(params.command, { shell: true, stdio: 'ignore' }).status === 0
}

function writeSkillsIndex() {
	if (succeeds({ command: 'dialecte skills generate' })) return
	console.warn('skills index not generated: run `npm run skills:generate`')
}

writeSkillsIndex()
