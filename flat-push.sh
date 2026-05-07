#!/bin/bash

BRANCH_PRINCIPAL="main"

echo "AVISO: Isso apagara TODO o historico de commits."
read -p "Continuar? (s/n): " confirm

if [[ $confirm != "s" ]]; then
    exit 1
fi

read -p "Mensagem do commit: " commit_msg

if [[ -z "$commit_msg" ]]; then
    commit_msg="Initial commit"
fi

git checkout --orphan branch-temporaria
git add -A
git commit -m "$commit_msg"
git branch -D $BRANCH_PRINCIPAL
git branch -m $BRANCH_PRINCIPAL

read -p "Forçar push para origin? (s/n): " push_confirm

if [[ $push_confirm == "s" ]]; then
    git push -f origin $BRANCH_PRINCIPAL
fi
