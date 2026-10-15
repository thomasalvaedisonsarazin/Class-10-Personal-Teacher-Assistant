import { Box } from '@chakra-ui/react';
import { motion, useReducedMotion, type Variants } from 'framer-motion';
import type { Key, ReactNode } from 'react';

export interface AnimatedListProps<T> {
  items: readonly T[];
  getKey: (item: T, index: number) => Key;
  renderItem: (item: T, index: number) => ReactNode;
  /** Chakra spacing token between items. */
  gap?: number;
}

const listVariants: Variants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.04 } },
};

const itemVariants: Variants = {
  hidden: { opacity: 0, y: 4 },
  show: { opacity: 1, y: 0, transition: { duration: 0.18, ease: 'easeOut' } },
};

/** List with a subtle stagger-in. Renders a semantic <ul>. */
export function AnimatedList<T>({ items, getKey, renderItem, gap = 3 }: AnimatedListProps<T>) {
  const reduceMotion = useReducedMotion();

  return (
    <Box asChild display="flex" flexDirection="column" gap={gap} listStyleType="none" m={0} p={0}>
      <motion.ul variants={listVariants} initial={reduceMotion ? false : 'hidden'} animate="show">
        {items.map((item, index) => (
          <motion.li key={getKey(item, index)} variants={itemVariants}>
            {renderItem(item, index)}
          </motion.li>
        ))}
      </motion.ul>
    </Box>
  );
}
