import { defineConfig } from 'vitepress'

export default defineConfig({
	title: '__packageName__',
	description: 'Dialecte SDK for __dialecteId__',
	themeConfig: {
		nav: [{ text: 'Guide', link: '/' }],
		sidebar: [
			{
				text: 'Introduction',
				items: [{ text: 'Getting started', link: '/' }],
			},
		],
	},
})
