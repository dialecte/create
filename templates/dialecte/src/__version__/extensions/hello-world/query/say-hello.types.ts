export type HelloWorldGreeting = {
	message: string
	/** Every element of the document, the root included. */
	elementCount: number
	/** How many elements of each kind the document holds; a kind it does not hold is left out. */
	countByTagName: Record<string, number>
}
