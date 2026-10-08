import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { deriveSingletons } from './derive-singletons.ts'

import type { DefinitionData, ElementData, ParticleData } from './derive.types.ts'

function element(params: { parents?: string[]; contentModel?: ParticleData } = {}): ElementData {
	const { parents = [], contentModel } = params
	const children = contentModel ? namesIn(contentModel) : []
	return {
		parents,
		attributes: { sequence: [], details: {} },
		children: {
			sequence: children,
			details: Object.fromEntries(children.map((child) => [child, {}])),
		},
		...(contentModel ? { contentModel } : {}),
	}
}

function namesIn(particle: ParticleData): string[] {
	if (particle.kind === 'element') return [particle.name]
	if (particle.kind === 'any') return []
	return particle.particles.flatMap(namesIn)
}

function once(name: string): ParticleData {
	return { kind: 'element', name, minOccurs: 1, maxOccurs: 1 }
}

function sequence(...particles: ParticleData[]): ParticleData {
	return { kind: 'sequence', minOccurs: 1, maxOccurs: 1, particles }
}

function choice(...particles: ParticleData[]): ParticleData {
	return { kind: 'choice', minOccurs: 1, maxOccurs: 1, particles }
}

/** The children of a parent holding `child` through its declaration `id`. */
function byReference(child: string, id: string): ElementData['children'] {
	return { sequence: [child], details: { [child]: { declarations: { 'urn:t': [id] } } } }
}

type SingletonCase = { definition: DefinitionData; root: string; expected: string[] }

const cases: Record<string, SingletonCase> = {
	'a child at most once under a root -> both are singletons': {
		definition: {
			Root: element({
				contentModel: { kind: 'sequence', minOccurs: 1, maxOccurs: 1, particles: [once('Header')] },
			}),
			Header: element({ parents: ['Root'] }),
		},
		root: 'Root',
		expected: ['Header', 'Root'],
	},
	'a child at most once in a group that repeats -> not a singleton (a flat table cannot see the group)':
		{
			definition: {
				Root: element({
					contentModel: {
						kind: 'sequence',
						minOccurs: 1,
						particles: [once('Entry'), once('Note')],
					},
				}),
				Entry: element({ parents: ['Root'] }),
				Note: element({ parents: ['Root'] }),
			},
			root: 'Root',
			expected: ['Root'],
		},
	'a child at most once under a parent that repeats -> not a singleton': {
		definition: {
			Root: element({
				contentModel: {
					kind: 'sequence',
					minOccurs: 1,
					maxOccurs: 1,
					particles: [{ kind: 'element', name: 'Item', minOccurs: 0 }],
				},
			}),
			Item: element({
				parents: ['Root'],
				contentModel: { kind: 'sequence', minOccurs: 1, maxOccurs: 1, particles: [once('Label')] },
			}),
			Label: element({ parents: ['Item'] }),
		},
		root: 'Root',
		expected: ['Root'],
	},
	'a child in two branches of one choice -> a singleton, a choice holds one branch': {
		definition: {
			Root: element({ contentModel: choice(once('Part'), sequence(once('Part'), once('Tail'))) }),
			Part: element({ parents: ['Root'] }),
			Tail: element({ parents: ['Root'] }),
		},
		root: 'Root',
		expected: ['Part', 'Root', 'Tail'],
	},
	'a child named twice in one sequence -> not a singleton': {
		definition: {
			Root: element({ contentModel: sequence(once('Part'), once('Tail'), once('Part')) }),
			Part: element({ parents: ['Root'] }),
			Tail: element({ parents: ['Root'] }),
		},
		root: 'Root',
		expected: ['Root', 'Tail'],
	},
	'a child once under each of two parents, one of them repeating -> not a singleton': {
		definition: {
			Root: element({
				contentModel: sequence(once('Single'), { kind: 'element', name: 'Many', minOccurs: 0 }),
			}),
			Single: element({ parents: ['Root'], contentModel: sequence(once('Shared')) }),
			Many: element({ parents: ['Root'], contentModel: sequence(once('Shared')) }),
			Shared: element({ parents: ['Single', 'Many'] }),
		},
		root: 'Root',
		expected: ['Root', 'Single'],
	},
	'an element no other holds, not the root -> not a singleton': {
		definition: {
			Root: element({ contentModel: sequence(once('Child')) }),
			Child: element({ parents: ['Root'] }),
			Loose: element(),
		},
		root: 'Root',
		expected: ['Child', 'Root'],
	},
	'a root that can nest in itself -> nothing is a singleton': {
		definition: {
			Folder: element({
				parents: ['Folder'],
				contentModel: sequence(once('Title'), {
					kind: 'element',
					name: 'Folder',
					minOccurs: 0,
					maxOccurs: 1,
				}),
			}),
			Title: element({ parents: ['Folder'] }),
		},
		root: 'Folder',
		expected: [],
	},
	'a child once in an xsi:type variant of a slot, which the slot model does not name -> a singleton':
		{
			definition: {
				Root: {
					...element({ contentModel: sequence(once('Address')) }),
					children: {
						sequence: ['Address'],
						details: {
							Address: {
								variants: {
									'{urn:t}tUsAddress': { contentModel: sequence(once('Street'), once('Zip')) },
									'{urn:t}tUkAddress': { contentModel: sequence(once('Street'), once('Postcode')) },
								},
							},
						},
					},
				},
				Address: element({ parents: ['Root'], contentModel: sequence(once('Street')) }),
				Street: element({ parents: ['Address'] }),
				Zip: element({ parents: ['Address'] }),
				Postcode: element({ parents: ['Address'] }),
			},
			root: 'Root',
			expected: ['Address', 'Postcode', 'Root', 'Street', 'Zip'],
		},
	'a child the content model does not name, admitted by a wildcard -> not a singleton': {
		definition: {
			Root: element({
				contentModel: {
					kind: 'sequence',
					minOccurs: 1,
					maxOccurs: 1,
					particles: [{ kind: 'any', minOccurs: 0 }],
				},
			}),
			Extra: { ...element({ parents: ['Root'] }) },
		},
		root: 'Root',
		expected: ['Root'],
	},
	'a child once in each declaration of a parent declared differently under two grandparents -> a singleton':
		{
			definition: {
				Root: element({
					contentModel: {
						kind: 'sequence',
						minOccurs: 1,
						maxOccurs: 1,
						particles: [once('Left'), once('Right')],
					},
				}),
				Left: {
					...element({ parents: ['Root'] }),
					children: {
						sequence: ['Part'],
						details: {
							Part: {
								attributes: { sequence: [], details: {} },
								children: { sequence: ['Leaf'], details: { Leaf: {} } },
								contentModel: {
									kind: 'sequence',
									minOccurs: 1,
									maxOccurs: 1,
									particles: [once('Leaf')],
								},
							},
						},
					},
					contentModel: { kind: 'sequence', minOccurs: 1, maxOccurs: 1, particles: [once('Part')] },
				},
				Right: {
					...element({ parents: ['Root'] }),
					children: {
						sequence: ['Part'],
						details: {
							Part: {
								attributes: { sequence: [], details: {} },
								children: { sequence: ['Leaf'], details: { Leaf: {} } },
								contentModel: {
									kind: 'sequence',
									minOccurs: 1,
									maxOccurs: 1,
									particles: [once('Leaf')],
								},
							},
						},
					},
					contentModel: { kind: 'sequence', minOccurs: 1, maxOccurs: 1, particles: [once('Part')] },
				},
				// the tag level: what any declaration allows, both declarations offered side by side
				Part: element({
					parents: ['Left', 'Right'],
					contentModel: {
						kind: 'choice',
						minOccurs: 1,
						maxOccurs: 1,
						particles: [once('Leaf'), once('Leaf')],
					},
				}),
				Leaf: element({ parents: ['Part'] }),
			},
			root: 'Root',
			expected: ['Leaf', 'Left', 'Part', 'Right', 'Root'],
		},
	'a child once in each way its parent is declared, referenced from the grandparents -> a singleton':
		{
			definition: {
				Root: element({ contentModel: sequence(once('Left'), once('Right')) }),
				Left: {
					...element({ parents: ['Root'], contentModel: sequence(once('Part')) }),
					children: byReference('Part', '1'),
				},
				Right: {
					...element({ parents: ['Root'], contentModel: sequence(once('Part')) }),
					children: byReference('Part', '2'),
				},
				// the tag level: the declarations disagree, so no content model
				Part: {
					...element({ parents: ['Left', 'Right'] }),
					declarations: {
						'1': {
							attributes: { sequence: [], details: {} },
							children: { sequence: ['Leaf'], details: {} },
							contentModel: sequence(once('Leaf')),
						},
						'2': {
							attributes: { sequence: [], details: {} },
							children: { sequence: ['Leaf', 'Other'], details: {} },
							contentModel: sequence(once('Leaf'), once('Other')),
						},
					},
				},
				Leaf: element({ parents: ['Part'] }),
				Other: element({ parents: ['Part'] }),
			},
			root: 'Root',
			expected: ['Leaf', 'Left', 'Other', 'Part', 'Right', 'Root'],
		},
	'a child once in each way its parent is declared, the grandparent naming no one way -> a singleton':
		{
			definition: {
				Root: element({ contentModel: sequence(once('Left')) }),
				// Part in two namespaces under Left: no one declaration to name
				Left: {
					...element({ parents: ['Root'], contentModel: sequence(once('Part')) }),
					children: {
						sequence: ['Part'],
						details: { Part: { declarations: { 'urn:a': ['1'], 'urn:b': ['2'] } } },
					},
				},
				Part: {
					...element({ parents: ['Left'] }),
					declarations: {
						'1': {
							attributes: { sequence: [], details: {} },
							children: { sequence: ['Leaf'], details: {} },
							contentModel: sequence(once('Leaf')),
						},
						'2': {
							attributes: { sequence: [], details: {} },
							children: { sequence: ['Leaf'], details: {} },
							contentModel: choice(once('Leaf')),
						},
					},
				},
				Leaf: element({ parents: ['Part'] }),
			},
			root: 'Root',
			expected: ['Leaf', 'Left', 'Part', 'Root'],
		},
	'a child once in each way its parent is declared and twice in an xsi:type variant -> not a singleton':
		{
			definition: {
				Root: element({ contentModel: sequence(once('Left')) }),
				Left: {
					...element({ parents: ['Root'], contentModel: sequence(once('Part')) }),
					children: {
						sequence: ['Part'],
						details: {
							Part: {
								declarations: { 'urn:t': ['1'] },
								variants: {
									'{urn:t}tTwice': { contentModel: sequence(once('Leaf'), once('Leaf')) },
								},
							},
						},
					},
				},
				Part: {
					...element({ parents: ['Left'] }),
					declarations: {
						'1': {
							attributes: { sequence: [], details: {} },
							children: { sequence: ['Leaf'], details: {} },
							contentModel: sequence(once('Leaf')),
						},
						'2': {
							attributes: { sequence: [], details: {} },
							children: { sequence: ['Leaf'], details: {} },
							contentModel: sequence(once('Leaf')),
						},
					},
				},
				Leaf: element({ parents: ['Part'] }),
			},
			root: 'Root',
			expected: ['Left', 'Part', 'Root'],
		},
	'a child once in one way its parent is declared and twice in the other -> not a singleton': {
		definition: {
			Root: element({ contentModel: sequence(once('Left'), once('Right')) }),
			Left: {
				...element({ parents: ['Root'], contentModel: sequence(once('Part')) }),
				children: byReference('Part', '1'),
			},
			Right: {
				...element({ parents: ['Root'], contentModel: sequence(once('Part')) }),
				children: byReference('Part', '2'),
			},
			Part: {
				...element({ parents: ['Left', 'Right'] }),
				declarations: {
					'1': {
						attributes: { sequence: [], details: {} },
						children: { sequence: ['Leaf'], details: {} },
						contentModel: sequence(once('Leaf')),
					},
					'2': {
						attributes: { sequence: [], details: {} },
						children: { sequence: ['Leaf'], details: {} },
						contentModel: sequence(once('Leaf'), once('Leaf')),
					},
				},
			},
			Leaf: element({ parents: ['Part'] }),
		},
		root: 'Root',
		expected: ['Left', 'Part', 'Right', 'Root'],
	},
	'a child once in one declaration of its parent and twice in the other -> not a singleton': {
		definition: {
			Root: element({ contentModel: sequence(once('Left'), once('Right')) }),
			Left: {
				...element({ parents: ['Root'], contentModel: sequence(once('Part')) }),
				children: {
					sequence: ['Part'],
					details: {
						Part: {
							attributes: { sequence: [], details: {} },
							children: { sequence: ['Leaf'], details: {} },
							contentModel: sequence(once('Leaf')),
						},
					},
				},
			},
			Right: {
				...element({ parents: ['Root'], contentModel: sequence(once('Part')) }),
				children: {
					sequence: ['Part'],
					details: {
						Part: {
							attributes: { sequence: [], details: {} },
							children: { sequence: ['Leaf'], details: {} },
							contentModel: sequence(once('Leaf'), once('Leaf')),
						},
					},
				},
			},
			Part: element({ parents: ['Left', 'Right'], contentModel: sequence(once('Leaf')) }),
			Leaf: element({ parents: ['Part'] }),
		},
		root: 'Root',
		expected: ['Left', 'Part', 'Right', 'Root'],
	},
	'a child once in one declaration of its parent, the other open to any element -> not a singleton':
		{
			definition: {
				Root: element({ contentModel: sequence(once('Left'), once('Right')) }),
				Left: {
					...element({ parents: ['Root'], contentModel: sequence(once('Part')) }),
					children: {
						sequence: ['Part'],
						details: {
							Part: {
								attributes: { sequence: [], details: {} },
								children: { sequence: ['Leaf'], details: {} },
								contentModel: sequence(once('Leaf')),
							},
						},
					},
				},
				Right: {
					...element({ parents: ['Root'], contentModel: sequence(once('Part')) }),
					children: {
						sequence: ['Part'],
						details: {
							Part: {
								attributes: { sequence: [], details: {} },
								children: { sequence: [], details: {} },
								contentModel: sequence({ kind: 'any', minOccurs: 0 }),
							},
						},
					},
				},
				Part: element({ parents: ['Left', 'Right'], contentModel: sequence(once('Leaf')) }),
				Leaf: element({ parents: ['Part'] }),
			},
			root: 'Root',
			expected: ['Left', 'Part', 'Right', 'Root'],
		},
	'a root reached again through another element -> nothing is a singleton': {
		definition: {
			Root: element({ parents: ['Wrapper'], contentModel: sequence(once('Wrapper')) }),
			Wrapper: element({
				parents: ['Root'],
				contentModel: sequence({ kind: 'element', name: 'Root', minOccurs: 0, maxOccurs: 1 }),
			}),
		},
		root: 'Root',
		expected: [],
	},
	'a child prohibited in an unbounded group -> occurs never, a singleton': {
		definition: {
			Root: element({
				contentModel: {
					kind: 'sequence',
					minOccurs: 0,
					particles: [{ kind: 'element', name: 'Gone', minOccurs: 0, maxOccurs: 0 }],
				},
			}),
			Gone: element({ parents: ['Root'] }),
		},
		root: 'Root',
		expected: ['Gone', 'Root'],
	},
}

describe('deriveSingletons', () => {
	for (const [name, testCase] of Object.entries(cases)) {
		it(name, () => {
			const { definition, root, expected } = testCase
			assert.deepEqual(deriveSingletons({ definition, root }), expected)
		})
	}
})
