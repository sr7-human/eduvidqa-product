import { useMutation } from '@tanstack/react-query';
import { askQuestion } from '../api/client';
import type { AskRequest, AskResponse } from '../types';

export function useAskQuestion() {
  return useMutation<AskResponse, Error, AskRequest>({
    mutationFn: askQuestion,
  });
}
